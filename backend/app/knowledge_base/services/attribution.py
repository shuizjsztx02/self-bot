"""
引用溯源模块

功能：
1. 来源追踪 - 追踪回答内容的来源文档
2. 引用生成 - 生成标准化的引用格式
3. 置信度评估 - 评估回答的可信度
"""
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SourceReference:
    """来源引用"""
    doc_id: str
    chunk_id: str
    content: str
    score: float
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    doc_name: Optional[str] = None
    kb_id: Optional[str] = None
    kb_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_citation(self, format: str = "standard") -> str:
        """生成引用文本"""
        if format == "standard":
            parts = []
            if self.doc_name:
                parts.append(self.doc_name)
            if self.page_number:
                parts.append(f"第{self.page_number}页")
            if self.section_title:
                parts.append(f"「{self.section_title}」")
            return " - ".join(parts) if parts else self.doc_id
        
        elif format == "academic":
            return f"[{self.doc_name or self.doc_id}]"
        
        elif format == "markdown":
            return f"[{self.doc_name or self.doc_id}](doc://{self.doc_id})"
        
        return self.doc_id


@dataclass
class CitationSegment:
    """引用片段 - 回答中的一个片段及其来源"""
    text: str
    sources: List[SourceReference]
    confidence: float
    start_char: int = 0
    end_char: int = 0


@dataclass
class RAGResponse:
    """RAG 响应 - 包含回答和来源引用"""
    answer: str
    sources: List[SourceReference]
    segments: List[CitationSegment]
    overall_confidence: float
    query: str
    rewritten_query: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def get_formatted_answer(self, include_citations: bool = True) -> str:
        """获取带引用的格式化回答"""
        if not include_citations:
            return self.answer
        
        result = self.answer
        
        if self.sources:
            result += "\n\n---\n**参考来源：**\n"
            seen = set()
            for i, source in enumerate(self.sources, 1):
                if source.doc_id not in seen:
                    seen.add(source.doc_id)
                    result += f"\n[{i}] {source.to_citation()}"
        
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "answer": self.answer,
            "sources": [
                {
                    "doc_id": s.doc_id,
                    "chunk_id": s.chunk_id,
                    "content": s.content[:200] + "..." if len(s.content) > 200 else s.content,
                    "score": s.score,
                    "page_number": s.page_number,
                    "section_title": s.section_title,
                    "doc_name": s.doc_name,
                }
                for s in self.sources
            ],
            "confidence": self.overall_confidence,
            "query": self.query,
            "rewritten_query": self.rewritten_query,
            "timestamp": self.timestamp.isoformat(),
        }


class SourceTracker:
    """
    来源追踪器
    
    追踪回答内容与来源文档的对应关系
    """
    
    def __init__(self, embedding_service: Optional[Any] = None):
        self.embedding_service = embedding_service
    
    def track_sources(
        self,
        answer: str,
        source_documents: List[Any],
    ) -> List[CitationSegment]:
        """
        追踪回答中的来源
        
        将回答分割为片段，并匹配到对应的来源文档
        """
        sentences = self._split_answer(answer)
        segments = []
        
        for sentence in sentences:
            if not sentence.strip():
                continue
            
            matched_sources = []
            best_score = 0.0
            
            for doc in source_documents:
                content = getattr(doc, 'content', '')
                score = self._calculate_relevance(sentence, content)
                
                if score > 0.3:
                    source_ref = self._create_source_reference(doc, score)
                    matched_sources.append(source_ref)
                    
                    if score > best_score:
                        best_score = score
            
            if matched_sources:
                matched_sources.sort(key=lambda x: x.score, reverse=True)
                matched_sources = matched_sources[:3]
                
                segments.append(CitationSegment(
                    text=sentence,
                    sources=matched_sources,
                    confidence=best_score,
                ))
        
        return segments
    
    def _split_answer(self, answer: str) -> List[str]:
        """分割回答为句子"""
        sentences = re.split(r'[。！？\n]', answer)
        return [s.strip() for s in sentences if s.strip()]
    
    def _calculate_relevance(self, sentence: str, source_content: str) -> float:
        """计算句子与来源内容的相关性"""
        sentence_words = set(re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', sentence.lower()))
        source_words = set(re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', source_content.lower()))
        
        if not sentence_words:
            return 0.0
        
        overlap = len(sentence_words & source_words)
        
        jaccard = overlap / len(sentence_words)
        
        return jaccard
    
    def _create_source_reference(self, doc: Any, score: float) -> SourceReference:
        """创建来源引用对象"""
        return SourceReference(
            doc_id=getattr(doc, 'doc_id', ''),
            chunk_id=getattr(doc, 'id', getattr(doc, 'chunk_id', '')),
            content=getattr(doc, 'content', ''),
            score=score,
            page_number=getattr(doc, 'page_number', None),
            section_title=getattr(doc, 'section_title', None),
            doc_name=getattr(doc, 'doc_name', None),
            kb_id=getattr(doc, 'kb_id', None),
            kb_name=getattr(doc, 'kb_name', None),
            metadata=getattr(doc, 'metadata', getattr(doc, 'extra_data', {})),
        )


class ConfidenceEvaluator:
    """
    置信度评估器
    
    评估 RAG 回答的可信度
    """
    
    def evaluate(
        self,
        answer: str,
        sources: List[SourceReference],
        segments: List[CitationSegment],
    ) -> float:
        """
        评估整体置信度
        
        考虑因素：
        1. 来源数量和质量
        2. 来源与回答的相关性
        3. 回答的完整性
        """
        if not sources:
            return 0.0
        
        source_scores = [s.score for s in sources]
        avg_source_score = sum(source_scores) / len(source_scores)
        
        source_count_factor = min(1.0, len(sources) / 3)
        
        if segments:
            segment_confidences = [s.confidence for s in segments]
            coverage = len(segments) / max(1, len(self._split_answer(answer)))
            avg_segment_confidence = sum(segment_confidences) / len(segment_confidences)
        else:
            coverage = 0.5
            avg_segment_confidence = avg_source_score
        
        overall = (
            0.3 * avg_source_score +
            0.2 * source_count_factor +
            0.2 * coverage +
            0.3 * avg_segment_confidence
        )
        
        return min(1.0, overall)
    
    def _split_answer(self, answer: str) -> List[str]:
        """分割回答"""
        return [s for s in re.split(r'[。！？\n]', answer) if s.strip()]


class CitationGenerator:
    """
    引用生成器
    
    生成标准化的引用格式
    """
    
    @staticmethod
    def generate_inline_citations(
        answer: str,
        segments: List[CitationSegment],
    ) -> str:
        """
        生成内联引用
        
        在回答中插入引用标记
        """
        result = answer
        
        offset = 0
        for segment in segments:
            if segment.sources:
                citation_nums = [f"[{i+1}]" for i in range(len(segment.sources))]
                citation_str = "".join(citation_nums[:2])
                
                pos = result.find(segment.text, offset)
                if pos != -1:
                    end_pos = pos + len(segment.text)
                    result = result[:end_pos] + citation_str + result[end_pos:]
                    offset = end_pos + len(citation_str)
        
        return result
    
    @staticmethod
    def generate_bibliography(
        sources: List[SourceReference],
        style: str = "standard",
    ) -> str:
        """
        生成参考文献列表
        """
        if not sources:
            return ""
        
        seen = set()
        unique_sources = []
        for s in sources:
            if s.doc_id not in seen:
                seen.add(s.doc_id)
                unique_sources.append(s)
        
        lines = ["**参考文献：**", ""]
        
        for i, source in enumerate(unique_sources, 1):
            if style == "standard":
                lines.append(f"[{i}] {source.to_citation('standard')}")
            elif style == "academic":
                lines.append(f"[{i}] {source.to_citation('academic')}")
            elif style == "markdown":
                lines.append(f"[{i}] {source.to_citation('markdown')}")
        
        return "\n".join(lines)


class SourceAttribution:
    """
    来源溯源主类
    
    整合所有溯源功能
    """
    
    def __init__(
        self,
        embedding_service: Optional[Any] = None,
    ):
        self.source_tracker = SourceTracker(embedding_service)
        self.confidence_evaluator = ConfidenceEvaluator()
        self.citation_generator = CitationGenerator()
    
    def create_response(
        self,
        answer: str,
        source_documents: List[Any],
        query: str,
        rewritten_query: Optional[str] = None,
    ) -> RAGResponse:
        """
        创建带溯源的 RAG 响应
        """
        segments = self.source_tracker.track_sources(answer, source_documents)
        
        sources = []
        for segment in segments:
            for source in segment.sources:
                if source not in sources:
                    sources.append(source)
        
        sources = list({s.chunk_id: s for s in sources}.values())
        sources.sort(key=lambda x: x.score, reverse=True)
        
        confidence = self.confidence_evaluator.evaluate(answer, sources, segments)
        
        return RAGResponse(
            answer=answer,
            sources=sources[:10],
            segments=segments,
            overall_confidence=confidence,
            query=query,
            rewritten_query=rewritten_query,
        )
    
    def format_response(
        self,
        response: RAGResponse,
        include_inline_citations: bool = False,
        citation_style: str = "standard",
    ) -> str:
        """
        格式化响应
        """
        if include_inline_citations:
            answer = self.citation_generator.generate_inline_citations(
                response.answer, response.segments
            )
        else:
            answer = response.answer
        
        bibliography = self.citation_generator.generate_bibliography(
            response.sources, citation_style
        )
        
        if bibliography:
            return f"{answer}\n\n{bibliography}"
        
        return answer

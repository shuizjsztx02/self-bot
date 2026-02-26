"""
上下文压缩模块

功能：
1. 相关片段提取 - 从检索结果中提取最相关的部分
2. Token 预算控制 - 确保上下文不超过 Token 限制
3. 冗余去除 - 移除重复或低价值内容
"""
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
import re
import logging
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class CompressionConfig:
    """压缩配置"""
    max_tokens: int = 4000
    min_relevance_score: float = 0.3
    max_documents: int = 10
    sentence_overlap: int = 1
    preserve_structure: bool = True


@dataclass
class CompressedDocument:
    """压缩后的文档"""
    id: str
    original_content: str
    compressed_content: str
    relevance_score: float
    source_metadata: Dict[str, Any] = field(default_factory=dict)
    preserved_sentences: List[str] = field(default_factory=list)


class SentenceSplitter:
    """
    句子分割器
    
    支持中英文混合文本的句子分割
    """
    
    SENTENCE_ENDINGS = r'[。！？.!?]'
    
    def split(self, text: str) -> List[str]:
        """将文本分割为句子"""
        if not text:
            return []
        
        sentences = []
        current = ""
        
        for char in text:
            current += char
            if re.match(self.SENTENCE_ENDINGS, char):
                sentences.append(current.strip())
                current = ""
        
        if current.strip():
            sentences.append(current.strip())
        
        return [s for s in sentences if s]


class RelevanceScorer:
    """
    相关性评分器
    
    计算句子与查询的相关性
    """
    
    def __init__(self, embedding_service: Optional[Any] = None):
        self.embedding_service = embedding_service
    
    async def score_sentence(
        self,
        query: str,
        sentence: str,
    ) -> float:
        """
        计算单个句子与查询的相关性
        
        策略：
        1. 关键词匹配（快速）
        2. 语义相似度（需要 embedding）
        """
        query_lower = query.lower()
        sentence_lower = sentence.lower()
        
        query_words = set(re.findall(r'[\u4e00-\u9fff]+|[a-z]+', query_lower))
        sentence_words = set(re.findall(r'[\u4e00-\u9fff]+|[a-z]+', sentence_lower))
        
        if not query_words:
            return 0.0
        
        overlap = len(query_words & sentence_words)
        keyword_score = overlap / len(query_words)
        
        if self.embedding_service:
            try:
                query_emb = await self.embedding_service.embed_text(query)
                sentence_emb = await self.embedding_service.embed_text(sentence)
                
                semantic_score = self._cosine_similarity(query_emb, sentence_emb)
                
                return 0.4 * keyword_score + 0.6 * semantic_score
            except Exception as e:
                logger.debug(f"Embedding scoring failed: {e}")
        
        return keyword_score
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        import math
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


class ContextCompressor:
    """
    上下文压缩器
    
    核心功能：
    1. 从检索结果中提取最相关的片段
    2. 控制 Token 预算
    3. 保持上下文连贯性
    """
    
    def __init__(
        self,
        config: Optional[CompressionConfig] = None,
        token_counter: Optional[Any] = None,
        embedding_service: Optional[Any] = None,
    ):
        self.config = config or CompressionConfig()
        self.token_counter = token_counter
        self.sentence_splitter = SentenceSplitter()
        self.relevance_scorer = RelevanceScorer(embedding_service)
    
    async def compress(
        self,
        query: str,
        documents: List[Any],
        max_tokens: Optional[int] = None,
    ) -> List[CompressedDocument]:
        """
        压缩文档列表
        
        Args:
            query: 查询文本
            documents: 文档列表（需有 content 和 score 属性）
            max_tokens: 最大 Token 数
        
        Returns:
            压缩后的文档列表
        """
        max_tokens = max_tokens or self.config.max_tokens
        documents = documents[:self.config.max_documents]
        
        if not documents:
            return []
        
        scored_sentences = []
        
        for doc in documents:
            doc_id = getattr(doc, 'id', getattr(doc, 'chunk_id', str(id(doc))))
            content = getattr(doc, 'content', '')
            score = getattr(doc, 'score', 1.0)
            metadata = getattr(doc, 'metadata', getattr(doc, 'extra_data', {}))
            
            sentences = self.sentence_splitter.split(content)
            
            for i, sentence in enumerate(sentences):
                relevance = await self.relevance_scorer.score_sentence(query, sentence)
                
                if relevance >= self.config.min_relevance_score:
                    scored_sentences.append({
                        'doc_id': doc_id,
                        'sentence': sentence,
                        'relevance': relevance,
                        'doc_score': score,
                        'metadata': metadata,
                        'position': i,
                    })
        
        scored_sentences.sort(
            key=lambda x: x['relevance'] * 0.7 + x['doc_score'] * 0.3,
            reverse=True
        )
        
        compressed_docs = {}
        current_tokens = 0
        
        for item in scored_sentences:
            doc_id = item['doc_id']
            sentence = item['sentence']
            
            sentence_tokens = self._count_tokens(sentence)
            
            if current_tokens + sentence_tokens > max_tokens:
                continue
            
            if doc_id not in compressed_docs:
                compressed_docs[doc_id] = {
                    'sentences': [],
                    'metadata': item['metadata'],
                    'original_content': '',
                    'doc_score': item['doc_score'],
                }
            
            compressed_docs[doc_id]['sentences'].append({
                'text': sentence,
                'relevance': item['relevance'],
                'position': item['position'],
            })
            
            current_tokens += sentence_tokens
        
        result = []
        for doc_id, data in compressed_docs.items():
            sentences = sorted(data['sentences'], key=lambda x: x['position'])
            sentence_texts = [s['text'] for s in sentences]
            
            compressed_content = ''.join(sentence_texts)
            
            result.append(CompressedDocument(
                id=doc_id,
                original_content=data['original_content'],
                compressed_content=compressed_content,
                relevance_score=data['doc_score'],
                source_metadata=data['metadata'],
                preserved_sentences=sentence_texts,
            ))
        
        return result
    
    def _count_tokens(self, text: str) -> int:
        """计算 Token 数量"""
        if self.token_counter:
            return self.token_counter.count_tokens(text)
        
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)
    
    async def compress_with_context(
        self,
        query: str,
        documents: List[Any],
        conversation_context: str,
        max_tokens: Optional[int] = None,
    ) -> Tuple[str, List[CompressedDocument]]:
        """
        压缩并整合对话上下文
        
        Returns:
            (formatted_context, compressed_documents)
        """
        max_tokens = max_tokens or self.config.max_tokens
        
        context_tokens = self._count_tokens(conversation_context)
        remaining_tokens = max_tokens - context_tokens - 200
        
        compressed_docs = await self.compress(
            query, documents, max_tokens=remaining_tokens
        )
        
        doc_contents = []
        for doc in compressed_docs:
            doc_contents.append(f"[来源: {doc.id}]\n{doc.compressed_content}")
        
        formatted_context = ""
        if conversation_context:
            formatted_context += f"【对话历史】\n{conversation_context}\n\n"
        
        if doc_contents:
            formatted_context += f"【相关知识】\n" + "\n\n".join(doc_contents)
        
        return formatted_context, compressed_docs


class RedundancyRemover:
    """
    冗余去除器
    
    移除重复或高度相似的内容
    """
    
    def __init__(self, similarity_threshold: float = 0.9):
        self.similarity_threshold = similarity_threshold
    
    def remove_duplicates(
        self,
        documents: List[CompressedDocument],
    ) -> List[CompressedDocument]:
        """移除重复文档"""
        if len(documents) <= 1:
            return documents
        
        unique_docs = [documents[0]]
        
        for doc in documents[1:]:
            is_duplicate = False
            
            for unique_doc in unique_docs:
                similarity = self._text_similarity(
                    doc.compressed_content,
                    unique_doc.compressed_content
                )
                
                if similarity >= self.similarity_threshold:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_docs.append(doc)
        
        return unique_docs
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度（Jaccard）"""
        words1 = set(re.findall(r'[\u4e00-\u9fff]+|[a-z]+', text1.lower()))
        words2 = set(re.findall(r'[\u4e00-\u9fff]+|[a-z]+', text2.lower()))
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0

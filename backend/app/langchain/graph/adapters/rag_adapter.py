"""
RAG 适配器

负责 RagService 结果与 SupervisorState 之间的转换
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class RagResult:
    """RAG 检索结果"""
    query: str
    rewritten_query: str
    context: str
    sources: List[Dict[str, Any]]
    entities: List[str]
    documents: List[Any]
    query_variations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "rewritten_query": self.rewritten_query,
            "context": self.context,
            "sources": self.sources,
            "entities": self.entities,
            "documents": self.documents,
            "query_variations": self.query_variations,
        }


class RagAdapter:
    """
    RAG 结果适配器
    
    负责 RagService 结果和 SupervisorState 之间转换
    """
    
    @staticmethod
    def to_state(result: Any, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 RAG 结果写入状态
        
        Args:
            result: RAG 结果 (RagProcessResult, dict)
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        if isinstance(result, dict):
            return {
                **state,
                "rag_context": result.get("context") or result.get("formatted_context", ""),
                "rag_sources": RagAdapter._normalize_sources(result.get("sources", [])),
                "rag_documents": result.get("documents", []),
                "rag_entities": result.get("entities", []),
                "rag_query_variations": result.get("query_variations", []),
                "rewritten_query": result.get("rewritten_query"),
            }
        
        if hasattr(result, 'formatted_context'):
            sources = []
            if hasattr(result, 'sources'):
                sources = result.sources
            elif hasattr(result, 'documents'):
                sources = result.documents
            
            documents = []
            if hasattr(result, 'documents'):
                documents = result.documents
            
            return {
                **state,
                "rag_context": result.formatted_context,
                "rag_sources": RagAdapter._normalize_sources(sources),
                "rag_documents": documents,
                "rag_entities": getattr(result, 'entities', []),
                "rag_query_variations": getattr(result, 'query_variations', []),
                "rewritten_query": getattr(result, 'rewritten_query', result.query),
            }
        
        if hasattr(result, 'context'):
            return {
                **state,
                "rag_context": result.context,
                "rag_sources": RagAdapter._normalize_sources(getattr(result, 'sources', [])),
                "rag_documents": getattr(result, 'documents', []),
                "rag_entities": getattr(result, 'entities', []),
                "rag_query_variations": getattr(result, 'query_variations', []),
                "rewritten_query": getattr(result, 'rewritten_query', result.query),
            }
        
        return state
    
    @staticmethod
    def from_state(state: Dict[str, Any]) -> Optional[RagResult]:
        """
        从状态提取 RAG 结果
        
        Args:
            state: 当前状态
            
        Returns:
            RagResult 实例或 None
        """
        if not state.get("rag_context"):
            return None
        
        return RagResult(
            query=state.get("query", ""),
            rewritten_query=state.get("rewritten_query", ""),
            context=state.get("rag_context", ""),
            sources=state.get("rag_sources", []),
            entities=state.get("rag_entities", []),
            documents=state.get("rag_documents", []),
            query_variations=state.get("rag_query_variations", []),
        )
    
    @staticmethod
    def format_context_for_prompt(state: Dict[str, Any]) -> str:
        """
        格式化 RAG 上下文用于提示词
        
        Args:
            state: 当前状态
            
        Returns:
            格式化后的上下文字符串
        """
        context = state.get("rag_context", "")
        if not context:
            return ""
        
        sources = state.get("rag_sources", [])
        
        parts = ["[知识库检索结果]"]
        parts.append(context)
        
        if sources:
            parts.append("\n[来源]")
            for i, source in enumerate(sources[:5], 1):
                title = source.get("title", "未知来源")
                score = source.get("score", 0)
                parts.append(f"{i}. {title} (相关度: {score:.2f})")
        
        return "\n".join(parts)
    
    @staticmethod
    def _normalize_sources(sources: List[Any]) -> List[Dict[str, Any]]:
        """
        标准化来源列表
        
        Args:
            sources: 来源列表
            
        Returns:
            标准化的字典列表
        """
        result = []
        for s in sources:
            if isinstance(s, dict):
                result.append({
                    "id": s.get("id", ""),
                    "title": s.get("title", ""),
                    "source_type": s.get("source_type", "kb"),
                    "score": s.get("score", 0),
                    "url": s.get("url"),
                    "content": s.get("content", "")[:500] if s.get("content") else "",
                })
            elif hasattr(s, 'id'):
                result.append({
                    "id": str(s.id) if hasattr(s.id, '__str__') else "",
                    "title": getattr(s, 'title', ''),
                    "source_type": getattr(s, 'source_type', 'kb'),
                    "score": getattr(s, 'score', 0),
                    "url": getattr(s, 'url', None),
                    "content": getattr(s, 'content', '')[:500] if hasattr(s, 'content') else "",
                })
            else:
                result.append({
                    "id": str(s),
                    "title": str(s),
                    "source_type": "unknown",
                    "score": 0,
                })
        return result

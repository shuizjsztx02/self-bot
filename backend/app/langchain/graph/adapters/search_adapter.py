"""
Search 适配器

负责互联网搜索结果与 SupervisorState 之间的转换
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """互联网搜索结果"""
    query: str
    context: str
    sources: List[Dict[str, Any]]
    iterations: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "context": self.context,
            "sources": self.sources,
            "iterations": self.iterations,
        }


class SearchAdapter:
    """
    搜索结果适配器
    
    负责在 ResearcherAgent 结果和 SupervisorState 之间转换
    """
    
    @staticmethod
    def to_state(result: Any, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        将搜索结果写入状态
        
        Args:
            result: 搜索结果 (str, dict, SearchResult)
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        if isinstance(result, str):
            return {
                **state,
                "search_context": result,
                "search_sources": [],
                "search_iterations": 1,
            }
        
        if isinstance(result, dict):
            return {
                **state,
                "search_context": result.get("context", result.get("result", "")),
                "search_sources": result.get("sources", []),
                "search_iterations": result.get("iterations", 1),
            }
        
        if hasattr(result, 'context'):
            return {
                **state,
                "search_context": result.context,
                "search_sources": getattr(result, 'sources', []),
                "search_iterations": getattr(result, 'iterations', 1),
            }
        
        if hasattr(result, '__str__'):
            return {
                **state,
                "search_context": str(result),
                "search_sources": [],
                "search_iterations": 1,
            }
        
        return state
    
    @staticmethod
    def from_state(state: Dict[str, Any]) -> Optional[SearchResult]:
        """
        从状态提取搜索结果
        
        Args:
            state: 当前状态
            
        Returns:
            SearchResult 实例或 None
        """
        if not state.get("search_context"):
            return None
        
        return SearchResult(
            query=state.get("query", ""),
            context=state.get("search_context", ""),
            sources=state.get("search_sources", []),
            iterations=state.get("search_iterations", 1),
        )
    
    @staticmethod
    def from_researcher_result(result: Any, query: str) -> SearchResult:
        """
        从 ResearcherAgent 结果创建 SearchResult
        
        Args:
            result: ResearcherAgent 返回的结果 (通常是 str)
            query: 原始查询
            
        Returns:
            SearchResult 实例
        """
        if isinstance(result, str):
            return SearchResult(
                query=query,
                context=result,
                sources=[],
                iterations=1,
            )
        
        if isinstance(result, dict):
            return SearchResult(
                query=query,
                context=result.get("context", result.get("result", "")),
                sources=result.get("sources", []),
                iterations=result.get("iterations", 1),
            )
        
        return SearchResult(
            query=query,
            context=str(result),
            sources=[],
            iterations=1,
        )
    
    @staticmethod
    def format_context_for_prompt(state: Dict[str, Any]) -> str:
        """
        格式化搜索上下文用于提示词
        
        Args:
            state: 当前状态
            
        Returns:
            格式化后的上下文字符串
        """
        context = state.get("search_context", "")
        if not context:
            return ""
        
        sources = state.get("search_sources", [])
        
        parts = ["[互联网搜索结果]"]
        parts.append(context)
        
        if sources:
            parts.append("\n[来源]")
            for i, source in enumerate(sources[:5], 1):
                title = source.get("title", "未知来源")
                url = source.get("url", "")
                parts.append(f"{i}. {title}")
                if url:
                    parts.append(f"   {url}")
        
        return "\n".join(parts)


class ParallelResultAdapter:
    """
    并行结果适配器
    
    处理 RAG 和 Search 并行执行的结果合并
    """
    
    @staticmethod
    def merge_results(
        rag_result: Optional[Any],
        search_result: Optional[Any],
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        合并并行执行结果
        
        Args:
            rag_result: RAG 结果
            search_result: 搜索结果
            state: 当前状态
            
        Returns:
            合并后的状态
        """
        from .rag_adapter import RagAdapter
        
        result = state.copy()
        
        if rag_result:
            result = RagAdapter.to_state(rag_result, result)
        
        if search_result:
            result = SearchAdapter.to_state(search_result, result)
        
        return result
    
    @staticmethod
    def format_combined_context(state: Dict[str, Any]) -> str:
        """
        格式化合并后的上下文
        
        Args:
            state: 当前状态
            
        Returns:
            格式化后的上下文字符串
        """
        from .rag_adapter import RagAdapter
        
        parts = []
        
        rag_context = RagAdapter.format_context_for_prompt(state)
        if rag_context:
            parts.append(rag_context)
        
        search_context = SearchAdapter.format_context_for_prompt(state)
        if search_context:
            parts.append(search_context)
        
        if not parts:
            return ""
        
        return "\n\n".join(parts)

"""
适配器子模块

提供各组件与状态之间的适配器
"""
from .intent_adapter import IntentAdapter, IntentResult
from .rag_adapter import RagAdapter, RagResult
from .search_adapter import SearchAdapter, SearchResult, ParallelResultAdapter
from .main_adapter import MainAgentAdapter, AgentResponse, ToolCallAdapter

__all__ = [
    "IntentAdapter",
    "IntentResult",
    "RagAdapter",
    "RagResult",
    "SearchAdapter",
    "SearchResult",
    "ParallelResultAdapter",
    "MainAgentAdapter",
    "AgentResponse",
    "ToolCallAdapter",
]

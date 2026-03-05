"""
适配器模块

负责各种 Service 结果与 SupervisorState 之间的转换
"""
from .intent_adapter import IntentAdapter, IntentResult, QueryIntent
from .rag_adapter import RagAdapter, RagResult
from .search_adapter import SearchAdapter, SearchResult, ParallelResultAdapter
from .main_adapter import MainAgentAdapter, AgentResponse, ToolCallAdapter

__all__ = [
    "IntentAdapter",
    "IntentResult",
    "QueryIntent",
    "RagAdapter",
    "RagResult",
    "SearchAdapter",
    "SearchResult",
    "ParallelResultAdapter",
    "MainAgentAdapter",
    "AgentResponse",
    "ToolCallAdapter",
]

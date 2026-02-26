"""
RAG 模块共享数据类型

定义被多个模块共享的数据类，降低模块间耦合
"""
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class ConversationTurn:
    """对话轮次"""
    role: str  # "user" or "assistant"
    content: str
    entities: List[str] = field(default_factory=list)
    intent: Optional[str] = None


@dataclass
class RewrittenQuery:
    """重写后的查询"""
    original_query: str
    rewritten_query: str
    variations: List[str] = field(default_factory=list)
    extracted_entities: List[str] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class QueryRewriteConfig:
    """查询重写配置"""
    max_history_turns: int = 5
    max_query_variations: int = 3
    enable_entity_extraction: bool = True
    enable_query_expansion: bool = True

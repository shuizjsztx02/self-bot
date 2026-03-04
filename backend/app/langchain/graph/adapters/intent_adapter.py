"""
意图分类适配器

负责 IntentResult 与 SupervisorState 之间的转换
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class QueryIntent(str, Enum):
    """查询意图枚举"""
    KB_QUERY = "kb_query"
    SEARCH_TASK = "search_task"
    DOCUMENT_TASK = "document_task"
    DATA_ANALYSIS = "data_analysis"
    CODE_TASK = "code_task"
    TOOL_TASK = "tool_task"
    GENERAL_CHAT = "general_chat"


@dataclass
class IntentResult:
    """意图分类结果"""
    intent: QueryIntent
    confidence: float
    kb_hints: List[str]
    reasoning: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent.value if self.intent else None,
            "confidence": self.confidence,
            "kb_hints": self.kb_hints,
            "reasoning": self.reasoning,
        }


class IntentAdapter:
    """
    意图分类结果适配器
    
    负责在 IntentResult 和 SupervisorState 之间转换
    """
    
    @staticmethod
    def to_state(result: Any, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 IntentResult 写入状态
        
        Args:
            result: 意图分类结果 (IntentResult 或 dict)
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        if isinstance(result, dict):
            return {
                **state,
                "intent": result.get("intent", {}).value if hasattr(result.get("intent"), "value") else result.get("intent"),
                "confidence": result.get("confidence"),
                "kb_hints": result.get("kb_hints", []),
            }
        
        return {
            **state,
            "intent": result.intent.value if result.intent else None,
            "confidence": result.confidence,
            "kb_hints": result.kb_hints,
        }
    
    @staticmethod
    def from_state(state: Dict[str, Any]) -> Optional[IntentResult]:
        """
        从状态提取 IntentResult
        
        Args:
            state: 当前状态
            
        Returns:
            IntentResult 实例或 None
        """
        intent_str = state.get("intent")
        if not intent_str:
            return None
        
        try:
            intent = QueryIntent(intent_str)
        except ValueError:
            intent = QueryIntent.GENERAL_CHAT
        
        return IntentResult(
            intent=intent,
            confidence=state.get("confidence", 0.0),
            kb_hints=state.get("kb_hints", []),
            reasoning=state.get("reasoning", ""),
        )
    
    @staticmethod
    def from_classifier_output(output: Dict[str, Any]) -> IntentResult:
        """
        从分类器输出创建 IntentResult
        
        Args:
            output: 分类器输出字典
            
        Returns:
            IntentResult 实例
        """
        intent_str = output.get("intent", "general_chat")
        
        try:
            intent = QueryIntent(intent_str)
        except ValueError:
            intent = QueryIntent.GENERAL_CHAT
        
        return IntentResult(
            intent=intent,
            confidence=output.get("confidence", 0.0),
            kb_hints=output.get("kb_hints", []),
            reasoning=output.get("reasoning", ""),
        )
    
    @staticmethod
    def determine_route(intent: QueryIntent, confidence: float) -> str:
        """
        根据意图和置信度确定路由
        
        Args:
            intent: 查询意图
            confidence: 置信度
            
        Returns:
            路由名称
        """
        if confidence < 0.65:
            return "parallel"
        
        route_map = {
            QueryIntent.KB_QUERY: "rag",
            QueryIntent.SEARCH_TASK: "search",
            QueryIntent.DOCUMENT_TASK: "direct",
            QueryIntent.DATA_ANALYSIS: "direct",
            QueryIntent.CODE_TASK: "direct",
            QueryIntent.TOOL_TASK: "direct",
            QueryIntent.GENERAL_CHAT: "direct",
        }
        
        return route_map.get(intent, "direct")

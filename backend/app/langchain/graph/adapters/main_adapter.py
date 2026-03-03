"""
Main Agent 适配器

负责 MainAgent 结果与 SupervisorState 之间的转换
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    """Agent 响应结果"""
    response: str
    tool_calls: List[Dict[str, Any]]
    tokens_used: int
    success: bool
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "response": self.response,
            "tool_calls": self.tool_calls,
            "tokens_used": self.tokens_used,
            "success": self.success,
            "error": self.error,
        }


class MainAgentAdapter:
    """
    Main Agent 结果适配器
    
    负责在 MainAgent 结果和 SupervisorState 之间转换
    """
    
    @staticmethod
    def to_state(result: Any, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 MainAgent 结果写入状态
        
        Args:
            result: MainAgent 结果 (dict, str, AgentResponse)
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        if isinstance(result, str):
            return {
                **state,
                "final_response": result,
                "tool_calls": [],
            }
        
        if isinstance(result, dict):
            return {
                **state,
                "final_response": result.get("output") or result.get("response") or result.get("content", ""),
                "tool_calls": result.get("tool_calls", []),
                "total_tokens": state.get("total_tokens", 0) + result.get("tokens_used", 0),
            }
        
        if hasattr(result, 'response'):
            return {
                **state,
                "final_response": result.response,
                "tool_calls": getattr(result, 'tool_calls', []),
                "total_tokens": state.get("total_tokens", 0) + getattr(result, 'tokens_used', 0),
            }
        
        if hasattr(result, 'content'):
            return {
                **state,
                "final_response": result.content,
                "tool_calls": [],
            }
        
        return state
    
    @staticmethod
    def from_state(state: Dict[str, Any]) -> Optional[AgentResponse]:
        """
        从状态提取 Agent 响应
        
        Args:
            state: 当前状态
            
        Returns:
            AgentResponse 实例或 None
        """
        if not state.get("final_response"):
            return None
        
        return AgentResponse(
            response=state.get("final_response", ""),
            tool_calls=state.get("tool_calls", []),
            tokens_used=state.get("total_tokens", 0),
            success=state.get("error") is None,
            error=state.get("error"),
        )
    
    @staticmethod
    def from_main_agent_result(result: Any) -> AgentResponse:
        """
        从 MainAgent 返回结果创建 AgentResponse
        
        Args:
            result: MainAgent.chat() 返回的结果
            
        Returns:
            AgentResponse 实例
        """
        if isinstance(result, dict):
            return AgentResponse(
                response=result.get("output") or result.get("response", ""),
                tool_calls=result.get("tool_calls", []),
                tokens_used=result.get("tokens_used", 0),
                success=True,
            )
        
        if isinstance(result, str):
            return AgentResponse(
                response=result,
                tool_calls=[],
                tokens_used=0,
                success=True,
            )
        
        if hasattr(result, 'output'):
            return AgentResponse(
                response=result.output,
                tool_calls=getattr(result, 'tool_calls', []),
                tokens_used=getattr(result, 'tokens_used', 0),
                success=True,
            )
        
        return AgentResponse(
            response=str(result),
            tool_calls=[],
            tokens_used=0,
            success=True,
        )
    
    @staticmethod
    def build_enhanced_query(state: Dict[str, Any]) -> str:
        """
        构建增强查询
        
        将 RAG 上下文或搜索上下文与原始查询合并
        
        Args:
            state: 当前状态
            
        Returns:
            增强后的查询字符串
        """
        query = state.get("query", "")
        
        rag_context = state.get("rag_context")
        search_context = state.get("search_context")
        
        if not rag_context and not search_context:
            return query
        
        parts = []
        
        if rag_context:
            parts.append("[知识库上下文]")
            parts.append(rag_context[:2000])
        
        if search_context:
            parts.append("[搜索上下文]")
            parts.append(search_context[:2000])
        
        parts.append("")
        parts.append("[用户问题]")
        parts.append(query)
        
        return "\n".join(parts)


class ToolCallAdapter:
    """
    工具调用适配器
    
    处理工具调用记录的转换
    """
    
    @staticmethod
    def normalize_tool_call(tool_call: Any) -> Dict[str, Any]:
        """
        标准化工具调用记录
        
        Args:
            tool_call: 工具调用 (dict 或其他格式)
            
        Returns:
            标准化的字典
        """
        if isinstance(tool_call, dict):
            return {
                "tool_name": tool_call.get("tool") or tool_call.get("name") or tool_call.get("tool_name", ""),
                "arguments": tool_call.get("args") or tool_call.get("arguments", {}),
                "result": tool_call.get("result"),
                "success": tool_call.get("success", True),
                "execution_time_ms": tool_call.get("execution_time_ms", 0),
                "error": tool_call.get("error"),
            }
        
        if hasattr(tool_call, 'tool'):
            return {
                "tool_name": getattr(tool_call, 'tool', getattr(tool_call, 'name', '')),
                "arguments": getattr(tool_call, 'args', getattr(tool_call, 'arguments', {})),
                "result": getattr(tool_call, 'result', None),
                "success": getattr(tool_call, 'success', True),
                "execution_time_ms": getattr(tool_call, 'execution_time_ms', 0),
                "error": getattr(tool_call, 'error', None),
            }
        
        return {
            "tool_name": str(tool_call),
            "arguments": {},
            "result": None,
            "success": True,
            "execution_time_ms": 0,
            "error": None,
        }
    
    @staticmethod
    def normalize_tool_calls(tool_calls: List[Any]) -> List[Dict[str, Any]]:
        """
        标准化工具调用列表
        
        Args:
            tool_calls: 工具调用列表
            
        Returns:
            标准化的列表
        """
        return [ToolCallAdapter.normalize_tool_call(tc) for tc in tool_calls]

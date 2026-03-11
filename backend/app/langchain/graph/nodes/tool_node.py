"""
工具节点模块

集成 LangGraph ToolNode，处理工具调用
"""
import time
import logging
from typing import Dict, Any, List, Optional

from langgraph.prebuilt import ToolNode
from langchain_core.tools import StructuredTool

from app.langchain.graph.state import SupervisorState, StateAdapter

logger = logging.getLogger(__name__)


def get_all_tools() -> List[StructuredTool]:
    """从 Registry 获取所有已加载的本地工具（同步）"""
    try:
        from app.langchain.tools import get_all_tools as _get_all_tools
        return _get_all_tools()
    except ImportError:
        logger.warning("[ToolNode] Could not import tools from app.langchain.tools")
        return []


def create_tool_node(tools: Optional[List[StructuredTool]] = None) -> ToolNode:
    """
    创建工具节点

    Args:
        tools: 预加载的工具列表；为 None 时只使用 Registry 中已加载的本地工具

    Returns:
        ToolNode 实例
    """
    if tools is None:
        tools = get_all_tools()

    logger.info(f"[ToolNode] Created with {len(tools)} tools")
    return ToolNode(tools)


async def execute_tools_node(state: SupervisorState) -> Dict[str, Any]:
    """
    执行工具调用节点
    
    处理消息中的工具调用
    
    Args:
        state: 当前状态
        
    Returns:
        更新后的状态片段
    """
    start_time = time.time()
    
    messages = state.get("messages", [])
    
    if not messages:
        return {"tool_calls": []}
    
    last_message = messages[-1]
    
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"tool_calls": []}
    
    logger.info(f"[ToolNode] Executing {len(last_message.tool_calls)} tool calls")
    
    try:
        tool_node = create_tool_node()
        
        result = await tool_node.ainvoke(state)
        
        tool_calls = []
        for tc in last_message.tool_calls:
            tool_calls.append({
                "tool_name": tc.get("name", tc.get("tool", "")),
                "arguments": tc.get("args", tc.get("arguments", {})),
                "executed": True,
            })
        
        duration_ms = (time.time() - start_time) * 1000
        
        state = StateAdapter.record_node_execution(
            state,
            node_name="execute_tools",
            success=True,
            duration_ms=duration_ms,
        )
        
        logger.info(f"[ToolNode] Tool execution completed (duration={duration_ms:.1f}ms)")
        
        return {
            "tool_calls": tool_calls,
            "messages": result.get("messages", []),
            "node_executions": state.get("node_executions", []),
        }
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"[ToolNode] Error: {e}")
        
        state = StateAdapter.record_node_execution(
            state,
            node_name="execute_tools",
            success=False,
            duration_ms=duration_ms,
            error=str(e),
        )
        
        return {
            "tool_calls": [],
            "error": str(e),
            "error_node": "execute_tools",
            "node_executions": state.get("node_executions", []),
        }


def should_continue(state: SupervisorState) -> str:
    """
    判断是否需要继续工具调用
    
    Args:
        state: 当前状态
        
    Returns:
        "tools" 或 "end"
    """
    messages = state.get("messages", [])
    
    if not messages:
        return "end"
    
    last_message = messages[-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
    return "end"


class ToolExecutor:
    """
    工具执行器
    
    提供便捷的工具执行接口
    """
    
    def __init__(self):
        self._tools: Dict[str, StructuredTool] = {}
        self._load_tools()
    
    def _load_tools(self):
        """从 Registry 加载所有已注册的本地工具"""
        for tool in get_all_tools():
            name = tool.name if hasattr(tool, 'name') else str(tool)
            self._tools[name] = tool
        logger.info(f"[ToolExecutor] Loaded {len(self._tools)} tools")
    
    def get_tool(self, name: str) -> Optional[StructuredTool]:
        """获取工具"""
        return self._tools.get(name)
    
    def list_tools(self) -> List[str]:
        """列出所有工具名称"""
        return list(self._tools.keys())
    
    async def execute(self, tool_name: str, **kwargs) -> Any:
        """
        执行工具
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
            
        Returns:
            工具执行结果
        """
        tool = self.get_tool(tool_name)
        
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")
        
        start_time = time.time()
        
        try:
            if hasattr(tool, 'ainvoke'):
                result = await tool.ainvoke(kwargs)
            elif hasattr(tool, 'invoke'):
                result = tool.invoke(kwargs)
            else:
                result = tool(**kwargs)
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info(f"[ToolExecutor] {tool_name} executed in {duration_ms:.1f}ms")
            
            return result
            
        except Exception as e:
            logger.error(f"[ToolExecutor] Error executing {tool_name}: {e}")
            raise

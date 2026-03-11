"""
工具模块公共接口

主要入口：
- get_all_tools()          同步，获取所有已加载的本地工具
- get_tools_for_query()    异步，根据用户查询动态选择工具（含 MCP 懒加载）
"""

from typing import List

from langchain_core.tools import BaseTool

from .metadata import ToolSource, ToolStatus, ToolMetadata, ToolEntry
from .registry import ToolRegistry, get_registry
from .initializer import ToolInitializer, initialize_tools, get_initializer, reset_initializer
from .selector import ToolSelectionResult, ToolSelector, get_tool_selector, reset_tool_selector


def get_all_tools() -> List[BaseTool]:
    """获取所有已加载的本地工具（同步）"""
    return get_registry().get_tools(source=ToolSource.LOCAL)


async def get_tools_for_query(query: str = "") -> List[BaseTool]:
    """
    根据用户查询动态选择工具（异步，触发 MCP 懒加载）

    这是 ChatService 的统一入口。选择器会：
    1. 始终包含核心工具（system/search/file 非危险）
    2. 根据 query 关键词按需加载扩展工具（含 MCP 服务器）
    """
    selector = await get_tool_selector()
    return await selector.get_tools_for_query(query)


__all__ = [
    "get_all_tools",
    "get_tools_for_query",
    "ToolSource", "ToolStatus", "ToolMetadata", "ToolEntry",
    "ToolRegistry", "get_registry",
    "ToolInitializer", "initialize_tools", "get_initializer", "reset_initializer",
    "ToolSelectionResult", "ToolSelector", "get_tool_selector", "reset_tool_selector",
]

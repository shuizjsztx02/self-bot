import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

from langchain_core.tools import BaseTool, StructuredTool

from app.langchain.tools.metadata import (
    ToolEntry,
    ToolMetadata,
    ToolSource,
    ToolStatus,
)

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    工具注册中心
    
    单例模式，统一管理所有工具的注册、加载和访问
    """
    
    _instance: Optional['ToolRegistry'] = None
    _initialized: bool = False
    
    def __new__(cls) -> 'ToolRegistry':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._entries: Dict[str, ToolEntry] = {}
        
        self._by_category: Dict[str, List[str]] = {}
        self._by_source: Dict[ToolSource, List[str]] = {}
        self._by_tag: Dict[str, List[str]] = {}
        self._mcp_servers: Dict[str, List[str]] = {}
        
        self._stats = {
            "total_registered": 0,
            "total_loaded": 0,
            "total_errors": 0,
        }
        
        self._initialized = True
        logger.info("[ToolRegistry] Initialized")
    
    @classmethod
    def get_instance(cls) -> 'ToolRegistry':
        """获取单例实例"""
        return cls()
    
    def _reset(self):
        """重置状态 (仅用于测试)"""
        self._entries.clear()
        self._by_category.clear()
        self._by_source.clear()
        self._by_tag.clear()
        self._mcp_servers.clear()
        self._stats = {
            "total_registered": 0,
            "total_loaded": 0,
            "total_errors": 0,
        }
    
    def _update_indexes(self, name: str, metadata: ToolMetadata):
        """更新索引"""
        if metadata.category not in self._by_category:
            self._by_category[metadata.category] = []
        self._by_category[metadata.category].append(name)
        
        if metadata.source not in self._by_source:
            self._by_source[metadata.source] = []
        self._by_source[metadata.source].append(name)
        
        for tag in metadata.tags:
            if tag not in self._by_tag:
                self._by_tag[tag] = []
            self._by_tag[tag].append(name)
        
        if metadata.mcp_server:
            if metadata.mcp_server not in self._mcp_servers:
                self._mcp_servers[metadata.mcp_server] = []
            self._mcp_servers[metadata.mcp_server].append(name)

    def _remove_from_indexes(self, name: str, metadata: ToolMetadata):
        """从索引中移除"""
        if metadata.category in self._by_category:
            if name in self._by_category[metadata.category]:
                self._by_category[metadata.category].remove(name)
        
        if metadata.source in self._by_source:
            if name in self._by_source[metadata.source]:
                self._by_source[metadata.source].remove(name)
        
        for tag in metadata.tags:
            if tag in self._by_tag and name in self._by_tag[tag]:
                self._by_tag[tag].remove(name)
        
        if metadata.mcp_server and metadata.mcp_server in self._mcp_servers:
            if name in self._mcp_servers[metadata.mcp_server]:
                self._mcp_servers[metadata.mcp_server].remove(name)

    def register(
        self,
        tool: Union[BaseTool, Callable],
        name: Optional[str] = None,
        category: str = "general",
        source: ToolSource = ToolSource.LOCAL,
        priority: int = 0,
        tags: Optional[List[str]] = None,
        lazy_load: bool = False,
        mcp_server: Optional[str] = None,
        dangerous: bool = False,
        description: Optional[str] = None,
    ) -> str:
        """
        注册工具
        
        Args:
            tool: 工具实例或可调用对象
            name: 工具名称
            category: 工具类别
            source: 工具来源
            priority: 优先级
            tags: 标签列表
            lazy_load: 是否懒加载
            mcp_server: MCP 服务器名称
            dangerous: 是否危险工具
            description: 工具描述
            
        Returns:
            工具名称
        """
        if not isinstance(tool, BaseTool):
            if callable(tool):
                tool = StructuredTool.from_function(
                    tool,
                    name=name or tool.__name__,
                    description=description or tool.__doc__ or "",
                )
            else:
                raise ValueError(f"Invalid tool type: {type(tool)}")
        
        tool_name = name or tool.name
        
        metadata = ToolMetadata(
            name=tool_name,
            description=description or tool.description,
            category=category,
            source=source,
            priority=priority,
            tags=tags or [],
            lazy_load=lazy_load,
            mcp_server=mcp_server,
            dangerous=dangerous,
        )
        
        entry = ToolEntry(
            metadata=metadata,
            tool=tool,
            status=ToolStatus.LOADED,
        )
        
        self._entries[tool_name] = entry
        self._update_indexes(tool_name, metadata)
        
        self._stats["total_registered"] += 1
        self._stats["total_loaded"] += 1
        
        logger.debug(f"[ToolRegistry] Registered: {tool_name}")
        return tool_name

    def register_loader(
        self,
        name: str,
        loader: Callable[[], Awaitable[BaseTool]],
        category: str = "general",
        source: ToolSource = ToolSource.LOCAL,
        priority: int = 0,
        tags: Optional[List[str]] = None,
        mcp_server: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        注册工具加载器 (延迟加载)
        
        Args:
            name: 工具名称
            loader: 异步加载函数
            category: 工具类别
            source: 工具来源
            priority: 优先级
            tags: 标签列表
            mcp_server: MCP 服务器名称
            
        Returns:
            工具名称
        """
        metadata = ToolMetadata(
            name=name,
            category=category,
            source=source,
            priority=priority,
            tags=tags or [],
            lazy_load=True,
            mcp_server=mcp_server,
        )
        
        entry = ToolEntry(
            metadata=metadata,
            tool=None,
            loader=loader,
            status=ToolStatus.REGISTERED,
        )
        
        self._entries[name] = entry
        self._update_indexes(name, metadata)
        
        self._stats["total_registered"] += 1
        logger.debug(f"[ToolRegistry] Registered loader: {name}")
        return name

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """
        获取单个工具 (同步)
        
        Args:
            name: 工具名称
            
        Returns:
            工具实例或 None
        """
        entry = self._entries.get(name)
        if entry and entry.tool:
            return entry.tool
        return None

    async def get_tool_async(self, name: str) -> Optional[Union[BaseTool, List[BaseTool]]]:
        """
        获取单个工具 (异步，支持懒加载)

        MCP sentinel 条目可能返回 List[BaseTool]，调用方需自行处理。

        Args:
            name: 工具名称

        Returns:
            BaseTool、List[BaseTool] 或 None
        """
        entry = self._entries.get(name)
        if entry is None:
            return None

        if entry.tool:
            return entry.tool

        if entry.loader:
            return await self._load_tool(name)

        return None

    def get_tools(
        self,
        names: Optional[List[str]] = None,
        category: Optional[str] = None,
        source: Optional[ToolSource] = None,
        tags: Optional[List[str]] = None,
    ) -> List[BaseTool]:
        """
        获取工具列表 (同步)
        
        Args:
            names: 指定工具名称列表
            category: 按类别过滤
            source: 按来源过滤
            tags: 按标签过滤
            
        Returns:
            工具列表
        """
        tools = []
        target_names = names or list(self._entries.keys())
        
        for name in target_names:
            entry = self._entries.get(name)
            if not entry or not entry.tool:
                continue
            
            if category and entry.metadata.category != category:
                continue
            if source and entry.metadata.source != source:
                continue
            if tags and not any(t in entry.metadata.tags for t in tags):
                continue
            
            tools.append(entry.tool)
        
        return tools

    async def get_tools_async(
        self,
        names: Optional[List[str]] = None,
        category: Optional[str] = None,
        source: Optional[ToolSource] = None,
        tags: Optional[List[str]] = None,
        load_lazy: bool = True,
    ) -> List[BaseTool]:
        """
        获取工具列表 (异步，支持懒加载)

        当 loader 返回 List[BaseTool]（如 MCP 批量加载）时，
        自动展开并追加到结果中。

        Args:
            names: 指定工具名称列表
            category: 按类别过滤
            source: 按来源过滤
            tags: 按标签过滤
            load_lazy: 是否加载懒加载工具

        Returns:
            工具列表
        """
        tools = []
        target_names = names or list(self._entries.keys())

        for name in target_names:
            entry = self._entries.get(name)
            if not entry:
                continue

            if category and entry.metadata.category != category:
                continue
            if source and entry.metadata.source != source:
                continue
            if tags and not any(t in entry.metadata.tags for t in tags):
                continue

            if load_lazy and entry.loader and not entry.tool:
                result = await self._load_tool(name)
                if isinstance(result, list):
                    tools.extend(result)
                elif result:
                    tools.append(result)
            elif entry.tool:
                if isinstance(entry.tool, list):
                    tools.extend(entry.tool)
                else:
                    tools.append(entry.tool)

        return tools

    def get_by_category(self, category: str) -> List[str]:
        """按类别获取工具名称列表"""
        return self._by_category.get(category, []).copy()

    def get_by_source(self, source: ToolSource) -> List[str]:
        """按来源获取工具名称列表"""
        return self._by_source.get(source, []).copy()

    def get_by_tag(self, tag: str) -> List[str]:
        """按标签获取工具名称列表"""
        return self._by_tag.get(tag, []).copy()

    def get_mcp_tools(self, server_name: str) -> List[str]:
        """获取 MCP 服务器工具名称列表"""
        return self._mcp_servers.get(server_name, []).copy()

    def list_tools(self) -> List[str]:
        """列出所有工具名称"""
        return list(self._entries.keys())

    def get_metadata(self, name: str) -> Optional[ToolMetadata]:
        """获取工具元数据"""
        entry = self._entries.get(name)
        return entry.metadata if entry else None

    def get_all_metadata(self) -> Dict[str, ToolMetadata]:
        """获取所有工具元数据"""
        return {name: entry.metadata for name, entry in self._entries.items()}

    async def _load_tool(self, name: str) -> Optional[Union[BaseTool, List[BaseTool]]]:
        """
        内部加载方法

        支持两种 loader 返回值：
        - 单个 BaseTool（普通工具）
        - List[BaseTool]（MCP 服务器等批量加载场景）
          批量情况下个别工具已在 loader 内部通过 register() 注册，
          此处仅标记 sentinel 条目为已触发，返回 list 供调用方展开。

        Returns:
            BaseTool、List[BaseTool] 或 None
        """
        entry = self._entries.get(name)
        if entry is None:
            logger.warning(f"[ToolRegistry] Tool not found: {name}")
            return None

        if entry.tool:
            return entry.tool

        if entry.loader is None:
            logger.warning(f"[ToolRegistry] No loader for tool: {name}")
            return None

        start_time = time.time()
        try:
            result = await entry.loader()
            load_time = time.time() - start_time

            if isinstance(result, list):
                # MCP loader：实际工具已在 loader 内部注册，此处标记 sentinel 已触发
                entry.status = ToolStatus.LOADED
                entry.load_time = load_time
                self._stats["total_loaded"] += 1
                logger.info(
                    f"[ToolRegistry] Loaded batch: {name} → "
                    f"{len(result)} tools ({load_time:.2f}s)"
                )
                return result
            else:
                entry.tool = result
                entry.status = ToolStatus.LOADED
                entry.load_time = load_time
                self._stats["total_loaded"] += 1
                logger.info(f"[ToolRegistry] Loaded: {name} ({load_time:.2f}s)")
                return result

        except Exception as e:
            entry.status = ToolStatus.ERROR
            entry.error_message = str(e)
            self._stats["total_errors"] += 1
            logger.error(f"[ToolRegistry] Failed to load {name}: {e}")
            return None

    async def load_tool(self, name: str) -> Optional[BaseTool]:
        """加载单个工具"""
        return await self._load_tool(name)

    async def load_tools(self, names: List[str]) -> List[BaseTool]:
        """批量加载工具"""
        tools = []
        for name in names:
            tool = await self._load_tool(name)
            if tool:
                tools.append(tool)
        return tools

    def get_status(self, name: str) -> Optional[ToolStatus]:
        """获取工具状态"""
        entry = self._entries.get(name)
        return entry.status if entry else None

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "by_category": {k: len(v) for k, v in self._by_category.items()},
            "by_source": {k.value: len(v) for k, v in self._by_source.items()},
        }

    def enable_tool(self, name: str) -> bool:
        """启用工具"""
        entry = self._entries.get(name)
        if entry and entry.status == ToolStatus.DISABLED:
            entry.status = ToolStatus.REGISTERED
            return True
        return False

    def disable_tool(self, name: str) -> bool:
        """禁用工具"""
        entry = self._entries.get(name)
        if entry:
            entry.status = ToolStatus.DISABLED
            return True
        return False

    def unregister(self, name: str) -> bool:
        """注销工具"""
        if name not in self._entries:
            return False
        
        entry = self._entries.pop(name)
        self._remove_from_indexes(name, entry.metadata)
        
        self._stats["total_registered"] -= 1
        if entry.status == ToolStatus.LOADED:
            self._stats["total_loaded"] -= 1
        
        logger.info(f"[ToolRegistry] Unregistered: {name}")
        return True


def get_registry() -> ToolRegistry:
    """获取注册中心单例"""
    return ToolRegistry.get_instance()

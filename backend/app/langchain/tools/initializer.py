"""
工具初始化器

从 manifest.py 动态导入本地工具，从 config.MCP_SERVERS 注册 MCP 懒加载器。
新增工具只需修改 manifest.py，无需改动此文件。
"""

import importlib
import logging
from typing import Optional

from app.langchain.tools.metadata import ToolSource
from app.langchain.tools.registry import get_registry
from app.langchain.tools.manifest import LOCAL_TOOL_MANIFEST

logger = logging.getLogger(__name__)


class ToolInitializer:
    """工具初始化器"""

    def __init__(self):
        self.registry = get_registry()
        self._initialized = False

    async def initialize(self) -> None:
        """初始化所有工具（幂等，重复调用无副作用）"""
        if self._initialized:
            logger.info("[ToolInitializer] Already initialized, skipping")
            return

        logger.info("[ToolInitializer] Starting initialization...")

        await self._register_from_manifest()
        await self._register_mcp_loaders()

        self._initialized = True

        stats = self.registry.get_stats()
        logger.info(f"[ToolInitializer] Completed: {stats}")

    async def _register_from_manifest(self) -> None:
        """从 LOCAL_TOOL_MANIFEST 动态导入并注册本地工具"""
        count = 0
        for module_path, func_name, category, tags, dangerous in LOCAL_TOOL_MANIFEST:
            try:
                module = importlib.import_module(module_path)
                tool = getattr(module, func_name)
                self.registry.register(
                    tool=tool,
                    category=category,
                    source=ToolSource.LOCAL,
                    tags=tags,
                    dangerous=dangerous,
                )
                count += 1
            except Exception as e:
                logger.error(
                    f"[ToolInitializer] Failed to register "
                    f"{module_path}.{func_name}: {e}"
                )

        logger.info(f"[ToolInitializer] Registered {count} local tools from manifest")

    async def _register_mcp_loaders(self) -> None:
        """从 settings.MCP_SERVERS 注册 MCP 工具懒加载器"""
        from app.config import settings

        for server_name, cfg in settings.MCP_SERVERS.items():
            loader = self._make_mcp_loader(server_name)
            self.registry.register_loader(
                name=f"_mcp_{server_name}_loader",
                loader=loader,
                category=cfg.get("category", server_name),
                source=ToolSource.MCP,
                tags=cfg.get("tags", []),
                mcp_server=server_name,
            )

        logger.info(
            f"[ToolInitializer] Registered {len(settings.MCP_SERVERS)} MCP lazy loaders"
        )

    def _make_mcp_loader(self, server_name: str):
        """创建 MCP 懒加载闭包，调用时触发子进程启动和工具注册"""
        async def loader():
            return await self._load_mcp_server(server_name)
        return loader

    async def _load_mcp_server(self, server_name: str) -> list:
        """加载指定 MCP 服务器的工具并注册到 Registry"""
        from app.mcp.client import get_mcp_tools
        from app.config import settings

        cfg = settings.MCP_SERVERS.get(server_name, {})
        category = cfg.get("category", server_name)

        try:
            tools = await get_mcp_tools(server_name)
            for tool in tools:
                if not self.registry.get_tool(tool.name):
                    self.registry.register(
                        tool=tool,
                        category=category,
                        source=ToolSource.MCP,
                        mcp_server=server_name,
                    )
            logger.info(
                f"[ToolInitializer] Loaded {len(tools)} tools from MCP server '{server_name}'"
            )
            return tools
        except Exception as e:
            logger.error(
                f"[ToolInitializer] Failed to load MCP server '{server_name}': {e}"
            )
            return []


_initializer: Optional[ToolInitializer] = None


async def initialize_tools() -> None:
    """初始化所有工具（应用启动时调用一次）"""
    global _initializer
    if _initializer is None:
        _initializer = ToolInitializer()
    await _initializer.initialize()


def get_initializer() -> ToolInitializer:
    """获取初始化器单例"""
    global _initializer
    if _initializer is None:
        _initializer = ToolInitializer()
    return _initializer


def reset_initializer():
    """重置初始化器（仅用于测试）"""
    global _initializer
    _initializer = None

"""
工具选择器

根据用户查询的关键词，从 ToolRegistry 动态选择工具子集传给 Agent，
避免将全量工具一次性传入 LLM（尤其是 MCP 工具数量很多时）。

核心工具（system/search/file 非危险）始终包含，
扩展工具（office/code/skill/MCP）按关键词触发按需加载。
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.langchain.tools.registry import get_registry
from app.langchain.tools.metadata import ToolSource

logger = logging.getLogger(__name__)


@dataclass
class ToolSelectionResult:
    """工具选择结果"""
    tool_names: List[str]
    categories: List[str]
    core_tools: List[str]
    extended_tools: List[str]
    reasoning: str
    total_count: int


class ToolSelector:
    """
    工具选择器

    核心工具在 initialize() 时从 Registry 按类别动态读取，
    扩展类别的关键词映射为静态领域知识（不依赖工具名）。
    """

    # 核心类别：始终包含（file 类排除危险工具，shell 类始终可用供 Skill 使用）
    CORE_CATEGORIES = ["system", "search", "shell"]

    # 扩展类别关键词映射（静态领域知识，新增 MCP 服务器只需在 config.MCP_SERVERS 里加即可）
    EXTENDED_KEYWORDS: Dict[str, List[str]] = {
        "file":         ["删除", "复制", "移动", "delete", "copy", "move", "文件管理"],
        "code":         ["执行代码", "运行代码", "python", "script", "脚本", "execute"],
        "skill":        ["clawhub", "技能", "skill", "热门技能", "安装技能", "搜索技能", "卸载技能", "已安装技能"],
        "office_word":  ["word", "文档", "docx", "doc"],
        "office_excel": ["excel", "表格", "xlsx", "数据处理", "spreadsheet"],
        "office_pptx":  ["ppt", "幻灯片", "pptx", "演示", "presentation"],
        "notion":       ["notion", "笔记"],
        "feishu":       ["飞书", "feishu", "lark"],
    }

    def __init__(self):
        self.registry = get_registry()
        self._core_names: List[str] = []
        self._initialized = False

    async def initialize(self) -> None:
        """从 Registry 构建核心工具名列表（Registry 必须先完成初始化）"""
        if self._initialized:
            return

        core_names = []
        for cat in self.CORE_CATEGORIES:
            core_names.extend(self.registry.get_by_category(cat))

        # file 类别：仅加入非危险工具
        for name in self.registry.get_by_category("file"):
            meta = self.registry.get_metadata(name)
            if meta and not meta.dangerous:
                core_names.append(name)

        self._core_names = core_names
        self._initialized = True

        logger.info(
            f"[ToolSelector] Initialized: {len(self._core_names)} core tools, "
            f"{len(self.EXTENDED_KEYWORDS)} extended keyword categories"
        )

    def select_tools(
        self,
        query: str,
        detected_categories: Optional[List[str]] = None,
        max_tools: int = 50,
    ) -> ToolSelectionResult:
        """
        根据查询关键词选择工具名列表（同步）

        Args:
            query: 用户查询文本
            detected_categories: 外部已检测到的类别（可叠加）
            max_tools: 最大工具数量上限

        Returns:
            ToolSelectionResult（仅包含工具名，不触发 MCP 加载）
        """
        selected = set(self._core_names)
        categories = set(detected_categories or [])

        query_lower = query.lower()
        for cat, keywords in self.EXTENDED_KEYWORDS.items():
            for kw in keywords:
                if kw in query_lower:
                    categories.add(cat)
                    break

        extended = []
        for cat in categories:
            for name in self.registry.get_by_category(cat):
                if name not in selected and len(selected) < max_tools:
                    selected.add(name)
                    extended.append(name)

        return ToolSelectionResult(
            tool_names=list(selected),
            categories=list(categories),
            core_tools=list(self._core_names),
            extended_tools=extended,
            reasoning=f"核心 {len(self._core_names)} + 扩展 {len(extended)}",
            total_count=len(selected),
        )

    async def get_tools_for_query(self, query: str = "") -> List[Any]:
        """
        根据查询动态选择并加载工具实例（异步，按需触发 MCP 懒加载）

        流程：
        1. 按关键词选出工具名（含 _mcp_xxx_loader sentinel）
        2. 通过 get_tools_async 触发 MCP loader，loader 内部注册实际工具
        3. 若有 MCP loader 被触发，重新查询以获取新注册的实际工具

        Args:
            query: 用户查询文本

        Returns:
            List[BaseTool]
        """
        from app.config import settings

        result = self.select_tools(query, max_tools=settings.TOOL_SELECTION_MAX_TOOLS)

        has_mcp_loaders = any(
            n.startswith("_mcp_") and n.endswith("_loader")
            for n in result.tool_names
        )

        tools = await self.registry.get_tools_async(names=result.tool_names)

        if has_mcp_loaders:
            # MCP loader 已触发并注册了实际工具，重新查询以获取它们
            result = self.select_tools(query, max_tools=settings.TOOL_SELECTION_MAX_TOOLS)
            actual_names = [
                n for n in result.tool_names
                if not (n.startswith("_mcp_") and n.endswith("_loader"))
            ]
            tools = await self.registry.get_tools_async(names=actual_names)

        logger.info(
            f"[ToolSelector] Query='{query[:50]}' → "
            f"{len(tools)} tools "
            f"(categories: {result.categories}, {result.reasoning})"
        )

        return tools


_tool_selector: Optional[ToolSelector] = None


async def get_tool_selector() -> ToolSelector:
    """获取工具选择器单例（懒初始化）"""
    global _tool_selector
    if _tool_selector is None:
        _tool_selector = ToolSelector()
        await _tool_selector.initialize()
    return _tool_selector


def reset_tool_selector():
    """重置选择器（仅用于测试）"""
    global _tool_selector
    _tool_selector = None

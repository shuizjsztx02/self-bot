"""
依赖检测引擎

检测技能所需的各类依赖是否在当前环境中已满足：
- pip 包（Python 库）
- npm 包（Node.js 模块）
- MCP Server（工具服务）
- tools（LangChain 工具）
- env（环境变量）
"""

import importlib.util
import os
import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from .base import Skill, SkillDependencies

logger = logging.getLogger(__name__)

# pip 包名 → Python 模块名的常见映射（pip 包名与 import 名不同的情况）
_PIP_TO_MODULE: Dict[str, str] = {
    "python-docx": "docx",
    "python-pptx": "pptx",
    "python-jose": "jose",
    "pyyaml": "yaml",
    "pillow": "PIL",
    "scikit-learn": "sklearn",
    "beautifulsoup4": "bs4",
    "notion-client": "notion_client",
    "opencv-python": "cv2",
    "aiohttp": "aiohttp",
}


def _pip_name_to_module(pip_name: str) -> str:
    """将 pip 包名转换为 Python import 模块名"""
    base_name = re.split(r'[><=!~]', pip_name)[0].strip()
    if base_name.lower() in _PIP_TO_MODULE:
        return _PIP_TO_MODULE[base_name.lower()]
    return base_name.replace("-", "_")


@dataclass
class DependencyCheckResult:
    """依赖检测结果"""
    satisfied: bool = True
    missing_pip: List[str] = field(default_factory=list)
    missing_npm: List[str] = field(default_factory=list)
    missing_mcp_servers: List[Dict[str, Any]] = field(default_factory=list)
    missing_tools: List[str] = field(default_factory=list)
    missing_env_vars: List[str] = field(default_factory=list)
    missing_bins: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "satisfied": self.satisfied,
            "missing_pip": self.missing_pip,
            "missing_npm": self.missing_npm,
            "missing_mcp_servers": self.missing_mcp_servers,
            "missing_tools": self.missing_tools,
            "missing_env_vars": self.missing_env_vars,
            "missing_bins": self.missing_bins,
        }

    def summary(self) -> str:
        parts = []
        if self.missing_pip:
            parts.append(f"pip: {', '.join(self.missing_pip)}")
        if self.missing_npm:
            parts.append(f"npm: {', '.join(self.missing_npm)}")
        if self.missing_mcp_servers:
            names = [s.get("name", "?") for s in self.missing_mcp_servers]
            parts.append(f"MCP: {', '.join(names)}")
        if self.missing_tools:
            parts.append(f"tools: {', '.join(self.missing_tools)}")
        if self.missing_env_vars:
            parts.append(f"env: {', '.join(self.missing_env_vars)}")
        if self.missing_bins:
            parts.append(f"bins: {', '.join(self.missing_bins)}")
        return "; ".join(parts) if parts else "all satisfied"

    def has_installable(self) -> bool:
        """是否有可自动安装的缺失项（pip/npm/mcp）"""
        return bool(self.missing_pip or self.missing_npm or self.missing_mcp_servers)


class DependencyResolver:
    """依赖检测引擎"""

    def __init__(self, available_tool_names: Optional[List[str]] = None):
        self._available_tools = set(available_tool_names or [])

    async def check(self, skill: Skill) -> DependencyCheckResult:
        """检测技能的所有依赖是否满足"""
        deps = skill.meta.get_dependencies()
        if not deps.has_any():
            return DependencyCheckResult(satisfied=True)

        result = DependencyCheckResult()

        result.missing_pip = self._check_pip(deps.pip)
        result.missing_npm = self._check_npm(deps.npm)
        result.missing_mcp_servers = self._check_mcp_servers(deps.mcp_servers)
        result.missing_tools = self._check_tools(deps.tools)
        result.missing_env_vars = self._check_env(deps.env)
        result.missing_bins = self._check_bins(deps.bins)

        result.satisfied = not any([
            result.missing_pip,
            result.missing_npm,
            result.missing_mcp_servers,
            result.missing_tools,
            result.missing_env_vars,
            result.missing_bins,
        ])

        if not result.satisfied:
            logger.info(f"[DependencyResolver] {skill.meta.name}: {result.summary()}")

        return result

    def _check_pip(self, packages: List[str]) -> List[str]:
        missing = []
        for pkg in packages:
            module_name = _pip_name_to_module(pkg)
            if importlib.util.find_spec(module_name) is None:
                missing.append(pkg)
        return missing

    def _check_npm(self, packages: List[str]) -> List[str]:
        # npm 包检测需要 Node.js，简化处理：检查 node_modules
        # 在实际场景中可以执行 npm list --json
        missing = []
        for pkg in packages:
            try:
                import subprocess
                result = subprocess.run(
                    ["npm", "list", pkg, "--json"],
                    capture_output=True, timeout=10,
                )
                if result.returncode != 0:
                    missing.append(pkg)
            except Exception:
                missing.append(pkg)
        return missing

    def _check_mcp_servers(self, servers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        missing = []
        for server in servers:
            name = server.get("name", "")
            module = server.get("module", "")
            if module:
                if importlib.util.find_spec(module) is None:
                    missing.append(server)
            elif name:
                missing.append(server)
        return missing

    def _check_tools(self, tools: List[str]) -> List[str]:
        if not self._available_tools:
            return tools
        return [t for t in tools if t not in self._available_tools]

    def _check_env(self, env_vars: List[str]) -> List[str]:
        return [v for v in env_vars if not os.environ.get(v)]

    def _check_bins(self, bins: List[str]) -> List[str]:
        import shutil
        return [b for b in bins if shutil.which(b) is None]

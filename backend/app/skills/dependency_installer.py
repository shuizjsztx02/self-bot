"""
依赖自动安装器

根据 DependencyCheckResult 中的缺失项，执行自动安装：
- pip install（Python 库）
- npm install（Node.js 模块）
- MCP Server 动态注册
- bins（系统二进制）：根据当前系统类型选择 brew（Mac/Linux）或 scoop（Windows）
"""

import asyncio
import os
import sys
import re
import shutil
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Awaitable, TYPE_CHECKING, Literal

from .dependency_resolver import DependencyCheckResult

if TYPE_CHECKING:
    from .base import Skill

logger = logging.getLogger(__name__)

# 平台类型：用于 bins 安装指令选择
PlatformKind = Literal["windows", "darwin", "linux"]


def get_current_platform() -> PlatformKind:
    """获取当前系统类型，用于选择对应的 bins 安装指令。"""
    plat = sys.platform
    if plat == "win32":
        return "windows"
    if plat == "darwin":
        return "darwin"
    if plat in ("linux", "linux2"):
        return "linux"
    # 其他（如 cygwin、freebsd）按 linux 处理，优先尝试 brew
    return "linux"

# 安全白名单：pip/npm 包名格式
_VALID_PKG_RE = re.compile(r'^[a-zA-Z0-9_\-\.]+(?:\[[\w,]+\])?(?:[><=!~]+[\d\.a-zA-Z\*]+)?$')
_VALID_NPM_PKG_RE = re.compile(r'^@?[a-zA-Z0-9_\-\.\/]+(?:@[\d\.a-zA-Z\-\^~]+)?$')

# bins 平台回退映射：技能 metadata 仅提供 brew（macOS）时，Windows 使用 scoop
# 格式: bin_name -> { platform: install_cmd }
# platform: "windows" | "darwin" | "linux"，"default" 为兜底
_BINS_FALLBACK: Dict[str, Dict[str, str]] = {
    "obsidian-cli": {
        "windows": "scoop bucket add scoop-yakitrak https://github.com/yakitrak/scoop-yakitrak.git 2>nul; scoop install notesmd-cli",
        "darwin": "brew install yakitrak/yakitrak/obsidian-cli",
        "linux": "brew install yakitrak/yakitrak/obsidian-cli",
        "default": "brew install yakitrak/yakitrak/obsidian-cli",
    },
    "notesmd-cli": {
        "windows": "scoop bucket add scoop-yakitrak https://github.com/yakitrak/scoop-yakitrak.git 2>nul; scoop install notesmd-cli",
        "darwin": "brew install yakitrak/yakitrak/obsidian-cli",
        "linux": "brew install yakitrak/yakitrak/obsidian-cli",
        "default": "brew install yakitrak/yakitrak/obsidian-cli",
    },
}

ProgressCallback = Callable[[str, str, float], Awaitable[None]]


@dataclass
class InstallResult:
    """安装结果"""
    success: bool = True
    pip_installed: List[str] = field(default_factory=list)
    pip_failed: List[str] = field(default_factory=list)
    npm_installed: List[str] = field(default_factory=list)
    npm_failed: List[str] = field(default_factory=list)
    mcp_registered: List[str] = field(default_factory=list)
    mcp_failed: List[str] = field(default_factory=list)
    bins_installed: List[str] = field(default_factory=list)
    bins_failed: List[str] = field(default_factory=list)
    bins_manual: List[Dict[str, str]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "pip_installed": self.pip_installed,
            "pip_failed": self.pip_failed,
            "npm_installed": self.npm_installed,
            "npm_failed": self.npm_failed,
            "mcp_registered": self.mcp_registered,
            "mcp_failed": self.mcp_failed,
            "bins_installed": self.bins_installed,
            "bins_failed": self.bins_failed,
            "bins_manual": self.bins_manual,
            "errors": self.errors,
        }


class DependencyInstaller:
    """依赖自动安装器"""

    def __init__(self, timeout: int = 120):
        self.timeout = timeout

    async def install_all(
        self,
        check_result: DependencyCheckResult,
        progress_callback: Optional[ProgressCallback] = None,
        skill: Optional["Skill"] = None,
    ) -> InstallResult:
        result = InstallResult()
        total_steps = (
            (1 if check_result.missing_pip else 0)
            + (1 if check_result.missing_npm else 0)
            + len(check_result.missing_mcp_servers)
            + (1 if check_result.missing_bins else 0)
        )
        current_step = 0

        if check_result.missing_bins and skill:
            if progress_callback:
                await progress_callback(
                    "bins", f"Installing binaries: {', '.join(check_result.missing_bins)}...",
                    current_step / max(total_steps, 1),
                )
            ok, installed, failed, manual = await self.install_bins(
                skill, check_result.missing_bins
            )
            result.bins_installed = installed
            result.bins_failed = failed
            result.bins_manual = manual
            if not ok and failed:
                result.success = False
                result.errors.append(f"bins install failed: {', '.join(failed)}")
            current_step += 1

        if check_result.missing_pip:
            if progress_callback:
                await progress_callback(
                    "pip", f"Installing {', '.join(check_result.missing_pip)}...",
                    current_step / max(total_steps, 1),
                )
            ok, installed, failed = await self.install_pip_packages(check_result.missing_pip)
            result.pip_installed = installed
            result.pip_failed = failed
            if not ok:
                result.success = False
                result.errors.append(f"pip install failed: {', '.join(failed)}")
            current_step += 1

        if check_result.missing_npm:
            if progress_callback:
                await progress_callback(
                    "npm", f"Installing {', '.join(check_result.missing_npm)}...",
                    current_step / max(total_steps, 1),
                )
            ok, installed, failed = await self.install_npm_packages(check_result.missing_npm)
            result.npm_installed = installed
            result.npm_failed = failed
            if not ok:
                result.success = False
                result.errors.append(f"npm install failed: {', '.join(failed)}")
            current_step += 1

        for server_config in check_result.missing_mcp_servers:
            name = server_config.get("name", "unknown")
            if progress_callback:
                await progress_callback(
                    "mcp", f"Registering MCP server: {name}...",
                    current_step / max(total_steps, 1),
                )
            ok = await self.register_mcp_server(server_config)
            if ok:
                result.mcp_registered.append(name)
            else:
                result.mcp_failed.append(name)
                result.success = False
                result.errors.append(f"MCP registration failed: {name}")
            current_step += 1

        if progress_callback:
            status = "done" if result.success else "partial"
            await progress_callback(status, "Installation complete", 1.0)

        return result

    async def install_bins(
        self, skill: "Skill", missing_bins: List[str]
    ) -> tuple[bool, List[str], List[str], List[Dict[str, str]]]:
        """
        尝试安装缺失的 bins。
        使用技能的 metadata.install 或回退映射。

        Returns:
            (all_ok, installed, failed, manual_instructions)
        """
        installed: List[str] = []
        failed: List[str] = []
        manual: List[Dict[str, str]] = []
        install_instructions = getattr(skill.meta, "install_instructions", []) or []

        for bin_name in missing_bins:
            cmd = self._resolve_bin_install_command(
                bin_name, install_instructions
            )
            if not cmd:
                manual.append({
                    "bin": bin_name,
                    "message": f"请在系统上手动安装 {bin_name}，参考技能文档。",
                })
                failed.append(bin_name)
                continue

            ok = await self._run_shell_install(cmd)
            if ok:
                # 验证是否真的安装成功
                if shutil.which(bin_name) or shutil.which(f"{bin_name}.exe"):
                    installed.append(bin_name)
                else:
                    failed.append(bin_name)
            else:
                failed.append(bin_name)

        return len(failed) == 0, installed, failed, manual

    def _resolve_bin_install_command(
        self, bin_name: str, install_instructions: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        根据当前系统类型解析 bin 的安装命令。
        - Windows: 优先使用技能中的 kind=scoop，否则用 _BINS_FALLBACK["windows"]
        - Mac/Linux: 优先使用技能中的 kind=brew，否则用 _BINS_FALLBACK
        """
        platform = get_current_platform()

        # 1. 优先从技能 install 指令中选取与当前平台匹配的项
        for inst in install_instructions:
            kind = inst.get("kind", "")
            bins = inst.get("bins") or []
            if bin_name not in bins and bin_name not in (b or "" for b in bins):
                continue

            formula = inst.get("formula", "").strip()
            if not formula:
                continue

            # Windows 使用 scoop
            if platform == "windows" and kind == "scoop":
                bucket = inst.get("bucket", "")
                bucket_url = inst.get("bucket_url", "")
                if bucket and bucket_url:
                    return f"scoop bucket add {bucket} {bucket_url} 2>nul; scoop install {formula}"
                return f"scoop install {formula}"

            # Mac/Linux 使用 brew
            if platform in ("darwin", "linux") and kind == "brew":
                return f"brew install {formula}"

        # 2. 技能仅提供 brew 时，Windows 无匹配项，使用平台回退映射
        fallback = _BINS_FALLBACK.get(bin_name) or _BINS_FALLBACK.get(
            bin_name.replace("_", "-")
        )
        if fallback:
            cmd = fallback.get(platform) or fallback.get("default")
            if cmd:
                logger.debug(
                    f"[Installer] 使用平台回退: {bin_name} @ {platform} -> {cmd[:60]}..."
                )
                return cmd
        return None

    async def _run_shell_install(self, command: str) -> bool:
        """执行安装命令（不受 sandbox 限制）。"""
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout
            )
            if proc.returncode == 0:
                logger.info(f"[Installer] bins install ok: {command[:80]}...")
                return True
            err = (stderr or b"").decode(errors="replace")[:500]
            logger.warning(f"[Installer] bins install failed (code {proc.returncode}): {err}")
            return False
        except asyncio.TimeoutError:
            logger.error("[Installer] bins install timeout")
            return False
        except Exception as e:
            logger.error(f"[Installer] bins install error: {e}")
            return False

    async def install_pip_packages(
        self, packages: List[str]
    ) -> tuple[bool, List[str], List[str]]:
        safe_packages = []
        for pkg in packages:
            if not _VALID_PKG_RE.match(pkg):
                logger.warning(f"[Installer] Rejected unsafe pip package name: {pkg!r}")
                continue
            safe_packages.append(pkg)

        if not safe_packages:
            return True, [], []

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "pip", "install", *safe_packages,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout
            )

            if proc.returncode == 0:
                logger.info(f"[Installer] pip installed: {safe_packages}")
                return True, safe_packages, []
            else:
                err = stderr.decode(errors="replace")
                logger.error(f"[Installer] pip install failed: {err[:500]}")
                return False, [], safe_packages
        except asyncio.TimeoutError:
            logger.error("[Installer] pip install timeout")
            return False, [], safe_packages
        except Exception as e:
            logger.error(f"[Installer] pip install error: {e}")
            return False, [], safe_packages

    async def install_npm_packages(
        self, packages: List[str]
    ) -> tuple[bool, List[str], List[str]]:
        safe_packages = []
        for pkg in packages:
            if not _VALID_NPM_PKG_RE.match(pkg):
                logger.warning(f"[Installer] Rejected unsafe npm package name: {pkg!r}")
                continue
            safe_packages.append(pkg)

        if not safe_packages:
            return True, [], []

        npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"

        try:
            proc = await asyncio.create_subprocess_exec(
                npm_cmd, "install", *safe_packages,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout
            )

            if proc.returncode == 0:
                logger.info(f"[Installer] npm installed: {safe_packages}")
                return True, safe_packages, []
            else:
                err = stderr.decode(errors="replace")
                logger.error(f"[Installer] npm install failed: {err[:500]}")
                return False, [], safe_packages
        except asyncio.TimeoutError:
            logger.error("[Installer] npm install timeout")
            return False, [], safe_packages
        except FileNotFoundError:
            logger.error("[Installer] npm not found")
            return False, [], safe_packages
        except Exception as e:
            logger.error(f"[Installer] npm install error: {e}")
            return False, [], safe_packages

    async def register_mcp_server(self, server_config: Dict[str, Any]) -> bool:
        """
        动态注册 MCP Server

        server_config 格式:
        {
            "name": "notion",
            "module": "notion_mcp",
            "command": "python -m notion_mcp stdio",
            "env": ["NOTION_API_KEY"]
        }
        """
        name = server_config.get("name", "")
        command = server_config.get("command", "")
        module_name = server_config.get("module", "")

        if not name:
            logger.error("[Installer] MCP server config missing 'name'")
            return False

        if not command and module_name:
            command = f"python -m {module_name} stdio"

        if not command:
            logger.error(f"[Installer] MCP server '{name}' missing 'command'")
            return False

        # 安全检查：只允许 python -m 或已知格式
        allowed_prefixes = ("python -m ", "node ", "npx ")
        if not any(command.startswith(p) for p in allowed_prefixes):
            logger.warning(f"[Installer] Rejected MCP command for security: {command!r}")
            return False

        env_vars = server_config.get("env", [])
        missing_env = [v for v in env_vars if not os.environ.get(v)]
        if missing_env:
            logger.warning(
                f"[Installer] MCP '{name}' needs env vars: {missing_env}. "
                "Registration will proceed but server may fail to start."
            )

        try:
            from app.mcp.client import MCPToolManager
            manager = MCPToolManager()
            if hasattr(manager, "register_server"):
                await manager.register_server(name=name, command=command)
                logger.info(f"[Installer] MCP server registered: {name}")
                return True
            else:
                logger.warning(
                    f"[Installer] MCPToolManager has no register_server method. "
                    f"MCP '{name}' config saved but not dynamically registered."
                )
                return False
        except Exception as e:
            logger.error(f"[Installer] MCP registration error for '{name}': {e}")
            return False

"""
沙箱化 Shell 执行工具

为 Skills 提供受限的命令行执行能力。通过白名单命令、参数黑名单、
超时控制和工作目录限制，确保安全性的同时让 Skills 能调用
git / curl / pip / npx / python 等外部程序。

安全模型：
  允许 = 命令在白名单中 AND 参数不含黑名单模式 AND 工作目录合法
"""

import asyncio
import logging
import os
import re
import shlex
import sys
from pathlib import Path
from typing import List, Optional, Set, Tuple

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)

# ─── 白名单：允许执行的命令（basename，不含路径） ───
ALLOWED_COMMANDS: Set[str] = {
    # 包管理
    "pip", "pip3", "npm", "npx", "node",
    "scoop", "brew",
    # 版本控制
    "git",
    # 网络
    "curl", "wget",
    # 脚本运行
    "python", "python3",
    # Skill 专用 CLI
    "notion-cli", "mcporter", "obsidian-cli", "notesmd-cli",
    # 通用工具
    "echo", "cat", "head", "tail", "ls", "dir",
    "grep", "find", "wc", "sort", "uniq",
    "jq", "which", "where", "whoami",
    "date", "env", "printenv",
}

# ─── 黑名单模式：匹配到任何一个就拒绝执行 ───
_DANGEROUS_PATTERNS: List[re.Pattern] = [
    re.compile(r'\brm\s+.*-\s*r', re.IGNORECASE),
    re.compile(r'\brm\s+-rf\b', re.IGNORECASE),
    re.compile(r'\bsudo\b', re.IGNORECASE),
    re.compile(r'\bchmod\b', re.IGNORECASE),
    re.compile(r'\bchown\b', re.IGNORECASE),
    re.compile(r'\bmkfs\b', re.IGNORECASE),
    re.compile(r'\bdd\s+if=', re.IGNORECASE),
    re.compile(r'\b>\s*/dev/', re.IGNORECASE),
    re.compile(r'\bformat\b', re.IGNORECASE),
    re.compile(r'\bshutdown\b', re.IGNORECASE),
    re.compile(r'\breboot\b', re.IGNORECASE),
    re.compile(r'\bkill\s+-9\b', re.IGNORECASE),
    re.compile(r'\bpkill\b', re.IGNORECASE),
    re.compile(r'\bkillall\b', re.IGNORECASE),
    re.compile(r';\s*rm\b'),
    re.compile(r'\|\s*sh\b'),
    re.compile(r'\|\s*bash\b'),
    re.compile(r'\beval\b'),
    re.compile(r'`[^`]+`'),           # 反引号命令注入
    re.compile(r'\$\([^)]+\)'),       # $() 命令替换
]

# 输出大小上限（字节）
MAX_OUTPUT_BYTES = 50_000

# 默认 / 最大超时（秒）
DEFAULT_TIMEOUT = 60
MAX_TIMEOUT = 300


def _get_workspace_root() -> str:
    workspace = settings.WORKSPACE_PATH
    if not os.path.isabs(workspace):
        from app.core.file_permission import get_project_root
        workspace = os.path.join(get_project_root(), workspace.lstrip("./"))
    return os.path.normpath(workspace)


def _get_skills_root() -> str:
    install_dir = settings.CLAWHUB_INSTALL_DIR
    if not os.path.isabs(install_dir):
        from app.core.file_permission import get_project_root
        install_dir = os.path.join(get_project_root(), install_dir.lstrip("./"))
    return os.path.normpath(install_dir)


def _resolve_working_dir(cwd: Optional[str]) -> Tuple[str, Optional[str]]:
    """
    解析并校验工作目录。

    Returns:
        (resolved_dir, error)  error 为 None 表示合法
    """
    workspace_root = _get_workspace_root()
    skills_root = _get_skills_root()

    if not cwd:
        os.makedirs(workspace_root, exist_ok=True)
        return workspace_root, None

    resolved = os.path.normpath(os.path.abspath(cwd))

    allowed_roots = [workspace_root, skills_root]
    for root in allowed_roots:
        if resolved.startswith(root):
            if not os.path.isdir(resolved):
                return "", f"工作目录不存在: {resolved}"
            return resolved, None

    return "", (
        f"工作目录 '{resolved}' 不在允许范围内。"
        f"允许的根目录: {allowed_roots}"
    )


def _extract_command_name(command: str) -> str:
    """从命令字符串中提取可执行文件 basename"""
    if sys.platform == "win32":
        parts = command.strip().split()
    else:
        try:
            parts = shlex.split(command)
        except ValueError:
            parts = command.strip().split()
    if not parts:
        return ""
    basename = os.path.basename(parts[0])
    # Windows: 去掉 .exe / .cmd 后缀
    for suffix in (".exe", ".cmd", ".bat", ".com"):
        if basename.lower().endswith(suffix):
            basename = basename[:-len(suffix)]
            break
    return basename.lower()


def _get_effective_allowed_commands() -> Set[str]:
    """
    合并静态白名单与所有已安装技能声明的 bins，确保新 skills 下载即可运行。
    """
    effective = set(ALLOWED_COMMANDS)
    try:
        from app.skills.bins_registry import get_all_skill_bins
        effective |= get_all_skill_bins()
    except Exception:
        pass
    return effective


def _check_command_safety(command: str) -> Optional[str]:
    """
    检查命令是否安全。

    Returns:
        错误信息（None 表示通过）
    """
    cmd_name = _extract_command_name(command)
    if not cmd_name:
        return "命令不能为空"

    allowed = _get_effective_allowed_commands()
    if cmd_name not in allowed:
        return (
            f"命令 '{cmd_name}' 不在白名单中。"
            f"允许的命令: {', '.join(sorted(allowed))}"
        )

    for pattern in _DANGEROUS_PATTERNS:
        if pattern.search(command):
            return f"命令包含危险模式，已拒绝: {pattern.pattern}"

    return None


def _truncate_output(text: str) -> str:
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= MAX_OUTPUT_BYTES:
        return text
    truncated = encoded[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
    return truncated + f"\n\n... [输出超过 {MAX_OUTPUT_BYTES} 字节，已截断]"


# ─── Pydantic Schema ───

class ShellCommandInput(BaseModel):
    """沙箱 Shell 命令输入"""
    command: str = Field(
        description=(
            "要执行的 shell 命令。"
            "仅允许白名单命令（pip/npm/npx/git/curl/python 等），"
            "禁止 sudo、rm -rf 等危险操作。"
        )
    )
    working_directory: Optional[str] = Field(
        default=None,
        description="工作目录（默认 workspace）。只能在 workspace 或 skills 目录下执行。",
    )
    timeout: int = Field(
        default=DEFAULT_TIMEOUT,
        description=f"超时时间（秒），默认 {DEFAULT_TIMEOUT}，最大 {MAX_TIMEOUT}",
    )


class PipInstallInput(BaseModel):
    """pip 安装输入"""
    packages: str = Field(
        description="要安装的 Python 包名（空格分隔多个，如 'akshare pandas'）"
    )


class NpxRunInput(BaseModel):
    """npx 命令输入"""
    command: str = Field(
        description="npx 后面的完整参数（如 'skills find research' 或 '-y @presto-ai/google-workspace-mcp'）"
    )
    working_directory: Optional[str] = Field(
        default=None,
        description="工作目录",
    )


# ─── Tool 实现 ───

@tool(args_schema=ShellCommandInput)
async def sandbox_shell(
    command: str,
    working_directory: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """在沙箱中执行 Shell 命令。支持 pip/npm/npx/git/curl/python 等白名单命令。
    用于 Skill 依赖安装、数据获取、外部 CLI 调用等场景。
    禁止 sudo、rm -rf 等危险操作。

    Args:
        command: 要执行的命令
        working_directory: 工作目录（默认 workspace）
        timeout: 超时秒数

    Returns:
        命令的 stdout + stderr 输出
    """
    safety_error = _check_command_safety(command)
    if safety_error:
        return f"🚫 安全检查未通过: {safety_error}"

    cwd, dir_error = _resolve_working_dir(working_directory)
    if dir_error:
        return f"🚫 工作目录错误: {dir_error}"

    timeout = min(max(timeout, 5), MAX_TIMEOUT)

    cmd_name = _extract_command_name(command)
    logger.info(f"[SandboxShell] Executing: {command[:120]} (cwd={cwd}, timeout={timeout}s)")

    try:
        if sys.platform == "win32":
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
        else:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )

        stdout_text = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        stderr_text = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

        combined = ""
        if stdout_text.strip():
            combined += stdout_text
        if stderr_text.strip():
            if combined:
                combined += "\n"
            combined += stderr_text

        combined = _truncate_output(combined)

        exit_code = proc.returncode
        if exit_code == 0:
            return combined if combined.strip() else "✅ 命令执行成功（无输出）"
        else:
            return f"⚠️ 命令退出码: {exit_code}\n{combined}"

    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return f"⏰ 命令超时（{timeout}s）。请增加 timeout 参数或简化命令。"
    except FileNotFoundError:
        return f"❌ 命令 '{cmd_name}' 未找到，请确认已安装。"
    except Exception as e:
        logger.error(f"[SandboxShell] Unexpected error: {e}", exc_info=True)
        return f"❌ 执行出错: {str(e)}"


@tool(args_schema=PipInstallInput)
async def pip_install(packages: str) -> str:
    """安装 Python 包（使用 pip）。用于为 Skill 安装缺失的 Python 依赖。

    Args:
        packages: 包名（空格分隔多个，如 'akshare pandas'）

    Returns:
        安装结果
    """
    pkg_list = packages.strip().split()
    if not pkg_list:
        return "❌ 请提供至少一个包名"

    for pkg in pkg_list:
        if not re.match(r'^[a-zA-Z0-9_\-\[\]>=<.,]+$', pkg):
            return f"🚫 包名 '{pkg}' 含有非法字符"

    cmd = f"{sys.executable} -m pip install {' '.join(pkg_list)}"
    logger.info(f"[pip_install] {cmd}")

    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=MAX_TIMEOUT
        )
        stdout_text = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        stderr_text = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

        output = _truncate_output(stdout_text + "\n" + stderr_text)

        if proc.returncode == 0:
            return f"✅ 成功安装: {', '.join(pkg_list)}\n{output}"
        else:
            return f"❌ 安装失败 (exit {proc.returncode}):\n{output}"
    except asyncio.TimeoutError:
        return f"⏰ pip install 超时（{MAX_TIMEOUT}s）"
    except Exception as e:
        return f"❌ 安装出错: {str(e)}"


@tool(args_schema=NpxRunInput)
async def npx_run(command: str, working_directory: Optional[str] = None) -> str:
    """执行 npx 命令。用于运行 Node.js CLI 工具（如 skills find/add、mcporter 等）。

    Args:
        command: npx 后面的参数（如 'skills find research'）
        working_directory: 工作目录

    Returns:
        命令输出
    """
    if not command.strip():
        return "❌ 请提供 npx 命令参数"

    full_cmd = f"npx {command}"

    safety_error = _check_command_safety(full_cmd)
    if safety_error:
        return f"🚫 安全检查未通过: {safety_error}"

    cwd, dir_error = _resolve_working_dir(working_directory)
    if dir_error:
        return f"🚫 工作目录错误: {dir_error}"

    logger.info(f"[npx_run] {full_cmd} (cwd={cwd})")

    try:
        proc = await asyncio.create_subprocess_shell(
            full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=MAX_TIMEOUT
        )
        stdout_text = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        stderr_text = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

        combined = _truncate_output(stdout_text + "\n" + stderr_text)

        if proc.returncode == 0:
            return combined if combined.strip() else "✅ 命令执行成功（无输出）"
        else:
            return f"⚠️ npx 退出码: {proc.returncode}\n{combined}"
    except asyncio.TimeoutError:
        return f"⏰ npx 命令超时（{MAX_TIMEOUT}s）"
    except FileNotFoundError:
        return "❌ npx 未找到，请确认 Node.js 已安装。"
    except Exception as e:
        return f"❌ 执行出错: {str(e)}"

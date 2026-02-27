"""
文件访问权限控制模块

被 file_tools 和 MCP 服务共享
"""
import os
from typing import Tuple, List, Optional
from pathlib import Path


def get_project_root() -> str:
    """获取项目根目录"""
    return str(Path(__file__).parent.parent.parent.parent)


def get_allowed_directories() -> List[str]:
    """获取允许访问的目录列表"""
    try:
        from app.config import settings
    except ImportError:
        return []
    
    allowed = []
    
    workspace = settings.WORKSPACE_PATH
    if not os.path.isabs(workspace):
        workspace = workspace.lstrip("./")
        workspace = os.path.join(get_project_root(), workspace)
    allowed.append(os.path.normpath(workspace))
    
    if settings.FILE_ACCESS_ALLOWED_DIRS:
        for dir_path in settings.FILE_ACCESS_ALLOWED_DIRS:
            if not os.path.isabs(dir_path):
                dir_path = dir_path.lstrip("./")
                dir_path = os.path.join(get_project_root(), dir_path)
            allowed.append(os.path.normpath(dir_path))
    
    return list(set(allowed))


def get_denied_directories() -> List[str]:
    """获取禁止访问的目录列表"""
    try:
        from app.config import settings
    except ImportError:
        return []
    
    denied = []
    
    if settings.FILE_ACCESS_DENIED_DIRS:
        for dir_path in settings.FILE_ACCESS_DENIED_DIRS:
            if not os.path.isabs(dir_path):
                dir_path = dir_path.lstrip("./")
                dir_path = os.path.join(get_project_root(), dir_path)
            denied.append(os.path.normpath(dir_path))
    
    return denied


def is_strict_mode() -> bool:
    """检查是否为严格模式"""
    try:
        from app.config import settings
        return settings.FILE_ACCESS_STRICT_MODE
    except ImportError:
        return False


def check_path_permission(path: str) -> Tuple[bool, str]:
    """
    检查路径访问权限
    
    Returns:
        (allowed: bool, reason: str)
    """
    normalized = os.path.normpath(os.path.abspath(path))
    
    denied_dirs = get_denied_directories()
    for denied in denied_dirs:
        if normalized.startswith(denied):
            return False, f"路径在禁止访问列表中: {denied}"
    
    if is_strict_mode():
        allowed_dirs = get_allowed_directories()
        for allowed in allowed_dirs:
            if normalized.startswith(allowed):
                return True, "访问允许"
        return False, f"严格模式下，路径不在允许列表中。允许的目录: {allowed_dirs}"
    
    return True, "访问允许"


def resolve_path_with_permission(path: str, base_dir: Optional[str] = None) -> Tuple[str, str]:
    """
    解析路径并检查权限
    
    Args:
        path: 输入路径
        base_dir: 基础目录（默认为 workspace）
    
    Returns:
        (resolved_path: str, error: str) - error 为空表示成功
    """
    try:
        from app.config import settings
    except ImportError:
        return path, ""
    
    if os.path.isabs(path):
        resolved = path
    elif path.startswith("./") or path.startswith("../"):
        resolved = os.path.abspath(path)
    else:
        if base_dir is None:
            base_dir = settings.WORKSPACE_PATH
            if not os.path.isabs(base_dir):
                base_dir = base_dir.lstrip("./")
                base_dir = os.path.join(get_project_root(), base_dir)
        resolved = os.path.join(base_dir, path)
    
    allowed, reason = check_path_permission(resolved)
    if not allowed:
        return "", f"文件访问权限拒绝: {reason}"
    
    return resolved, ""


def validate_file_path(filepath: str) -> Tuple[bool, str, str]:
    """
    验证文件路径权限（MCP 工具使用）
    
    Args:
        filepath: 输入文件路径
    
    Returns:
        (is_valid: bool, resolved_path: str, error_message: str)
    """
    resolved, error = resolve_path_with_permission(filepath)
    if error:
        return False, "", error
    return True, resolved, ""


def get_permission_info() -> dict:
    """获取权限配置信息"""
    return {
        "strict_mode": is_strict_mode(),
        "allowed_directories": get_allowed_directories(),
        "denied_directories": get_denied_directories(),
        "project_root": get_project_root(),
    }

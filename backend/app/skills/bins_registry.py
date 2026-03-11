"""
技能 bins 注册表

收集所有已安装技能声明的 bins 依赖，供 sandbox_shell 白名单动态合并使用。
确保新安装的 skills 声明的命令（如 obsidian-cli）自动加入 sandbox_shell 白名单，下载即可运行。
"""

import logging
from typing import Set

logger = logging.getLogger(__name__)


def get_all_skill_bins() -> Set[str]:
    """
    从所有已加载的技能中收集 bins 依赖，合并为允许执行的命令集合。

    Returns:
        技能声明的 bins 命令名集合（小写）
    """
    bins: Set[str] = set()
    try:
        from app.core.managers import get_skill_manager

        manager = get_skill_manager()
        if not manager or not manager.loader:
            return bins

        for skill in manager.loader.get_all_cached().values():
            if not skill.meta.enabled:
                continue
            deps = skill.meta.get_dependencies()
            for b in deps.bins or []:
                if b and isinstance(b, str):
                    bins.add(b.strip().lower())
    except Exception as e:
        logger.debug(f"[BinsRegistry] Failed to collect skill bins: {e}")
    return bins

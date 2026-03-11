"""
全局管理器模块

提供全局共享的管理器实例，确保 API 和 Agent 使用同一实例
"""

from typing import Optional
import asyncio


class GlobalManagers:
    """
    全局管理器容器
    
    单例模式，存储所有共享的管理器实例
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._skill_manager = None
        self._state_manager = None
        self._mcp_tool_manager = None
        self._lock = asyncio.Lock()
        self._initialized = True
    
    @property
    def skill_manager(self):
        if self._skill_manager is None:
            from app.skills import SkillManager
            from app.config import settings
            from pathlib import Path

            base_path = Path(__file__).parent.parent
            skills_dirs = [
                str(base_path / "skills"),
                str(base_path / "skills_data"),
            ]
            self._skill_manager = SkillManager(
                skills_dir=skills_dirs,
                clawhub_install_dir=settings.CLAWHUB_INSTALL_DIR,
                clawhub_mock_mode=settings.CLAWHUB_USE_MOCK,
            )
        return self._skill_manager
    
    @property
    def state_manager(self):
        if self._state_manager is None:
            from app.langchain.services.state import AgentStateManager
            self._state_manager = AgentStateManager()
        return self._state_manager
    
    @property
    def mcp_tool_manager(self):
        if self._mcp_tool_manager is None:
            from app.mcp.client import MCPToolManager
            self._mcp_tool_manager = MCPToolManager()
        return self._mcp_tool_manager
    
    async def initialize_all(self):
        """初始化所有管理器"""
        async with self._lock:
            if self._skill_manager:
                await self._skill_manager.initialize()
    
    async def cleanup_all(self):
        """清理所有管理器"""
        async with self._lock:
            if self._mcp_tool_manager:
                await self._mcp_tool_manager.stop_all()


def get_global_managers() -> GlobalManagers:
    """获取全局管理器实例"""
    return GlobalManagers()


def get_skill_manager():
    """获取全局 Skill 管理器"""
    return get_global_managers().skill_manager


def set_skill_manager(manager) -> None:
    """
    覆盖全局 Skill 管理器实例（主要用于测试 / 热重载场景）

    Args:
        manager: SkillManager 实例，传 None 可重置为下次懒加载新建
    """
    get_global_managers()._skill_manager = manager


def get_state_manager():
    """获取全局状态管理器"""
    return get_global_managers().state_manager


def get_mcp_tool_manager():
    """获取全局 MCP 工具管理器"""
    return get_global_managers().mcp_tool_manager

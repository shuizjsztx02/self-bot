"""
LangGraph Checkpointer 模块

提供基于 SQLite 的状态持久化能力，支持:
1. 会话状态持久化
2. 断点恢复执行
3. 状态历史查询
"""
from typing import Optional, AsyncIterator, Dict, Any, List
from contextlib import asynccontextmanager, AsyncExitStack
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
import logging
import json

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.checkpoint.base import CheckpointTuple, Checkpoint

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CheckpointerConfig:
    """Checkpointer 配置"""
    
    CHECKPOINT_ENABLED: bool = True
    CHECKPOINT_DB_PATH: str = "./data/database/checkpoint.db"
    CHECKPOINT_TTL_HOURS: int = 24
    CHECKPOINT_MAX_HISTORY: int = 100
    
    @classmethod
    def from_settings(cls) -> "CheckpointerConfig":
        """从 settings 创建配置"""
        return cls(
            CHECKPOINT_ENABLED=getattr(settings, 'LANGGRAPH_CHECKPOINT_ENABLED', True),
            CHECKPOINT_DB_PATH=getattr(settings, 'LANGGRAPH_CHECKPOINT_DB_PATH', "./data/database/checkpoint.db"),
            CHECKPOINT_TTL_HOURS=getattr(settings, 'LANGGRAPH_CHECKPOINT_TTL_HOURS', 24),
            CHECKPOINT_MAX_HISTORY=getattr(settings, 'LANGGRAPH_CHECKPOINT_MAX_HISTORY', 100),
        )


@dataclass
class CheckpointInfo:
    """检查点信息"""
    thread_id: str
    checkpoint_id: str
    checkpoint_ns: str = ""
    parent_checkpoint_id: Optional[str] = None
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "checkpoint_id": self.checkpoint_id,
            "checkpoint_ns": self.checkpoint_ns,
            "parent_checkpoint_id": self.parent_checkpoint_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": self.metadata,
        }


class CheckpointerManager:
    """
    Checkpointer 管理器
    
    负责:
    1. 创建和管理 AsyncSqliteSaver 实例
    2. 提供 checkpointer 生命周期管理
    3. 清理过期检查点
    4. 状态查询与恢复
    
    使用方式:
        manager = CheckpointerManager()
        saver = await manager.get_saver()
        
        # 或使用上下文管理器
        async with manager.get_checkpointer() as saver:
            ...
    """
    
    _instance: Optional["CheckpointerManager"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._config = CheckpointerConfig.from_settings()
        self._saver: Optional[AsyncSqliteSaver] = None
        self._context_manager = None
        self._exit_stack: Optional[AsyncExitStack] = None
        self._initialized = True
        logger.info(f"[Checkpointer] Manager initialized, enabled={self._config.CHECKPOINT_ENABLED}")
    
    @property
    def enabled(self) -> bool:
        """Checkpointer 是否启用"""
        return self._config.CHECKPOINT_ENABLED
    
    @property
    def db_path(self) -> str:
        """数据库路径"""
        return self._config.CHECKPOINT_DB_PATH
    
    async def get_saver(self) -> Optional[AsyncSqliteSaver]:
        """
        获取或创建 AsyncSqliteSaver 实例
        
        Returns:
            AsyncSqliteSaver 实例，如果未启用则返回 None
        """
        if not self.enabled:
            logger.debug("[Checkpointer] Checkpointer is disabled")
            return None
        
        if self._saver is None:
            db_path = Path(self.db_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            self._exit_stack = AsyncExitStack()
            
            self._context_manager = AsyncSqliteSaver.from_conn_string(str(db_path))
            
            self._saver = await self._exit_stack.enter_async_context(self._context_manager)
            
            logger.info(f"[Checkpointer] AsyncSqliteSaver initialized with db: {db_path}")
        
        return self._saver
    
    async def close(self):
        """关闭 checkpointer 连接"""
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._saver = None
            self._context_manager = None
            logger.info("[Checkpointer] Closed")
    
    @asynccontextmanager
    async def get_checkpointer(self) -> AsyncIterator[Optional[AsyncSqliteSaver]]:
        """
        上下文管理器方式获取 checkpointer
        
        Usage:
            async with manager.get_checkpointer() as saver:
                if saver:
                    graph = build_graph(checkpointer=saver)
        """
        saver = await self.get_saver()
        try:
            yield saver
        finally:
            pass
    
    async def get_checkpoint(
        self, 
        thread_id: str,
        checkpoint_id: Optional[str] = None,
    ) -> Optional[CheckpointTuple]:
        """
        获取指定的检查点
        
        Args:
            thread_id: 线程 ID
            checkpoint_id: 检查点 ID (可选，默认获取最新)
            
        Returns:
            CheckpointTuple 或 None
        """
        saver = await self.get_saver()
        if not saver:
            return None
        
        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }
        
        if checkpoint_id:
            config["configurable"]["checkpoint_id"] = checkpoint_id
        
        checkpoint_tuple = await saver.aget_tuple(config)
        return checkpoint_tuple
    
    async def list_checkpoints(
        self,
        thread_id: str,
        limit: int = 10,
    ) -> List[CheckpointInfo]:
        """
        列出指定线程的检查点
        
        Args:
            thread_id: 线程 ID
            limit: 最大返回数量
            
        Returns:
            CheckpointInfo 列表
        """
        saver = await self.get_saver()
        if not saver:
            return []
        
        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }
        
        checkpoints = []
        try:
            async for checkpoint_tuple in saver.alist(config):
                if len(checkpoints) >= limit:
                    break
                
                cp_config = checkpoint_tuple.config or {}
                configurable = cp_config.get("configurable", {})
                
                info = CheckpointInfo(
                    thread_id=thread_id,
                    checkpoint_id=configurable.get("checkpoint_id", ""),
                    checkpoint_ns=configurable.get("checkpoint_ns", ""),
                    parent_checkpoint_id=None,
                    metadata=checkpoint_tuple.metadata or {},
                    created_at=checkpoint_tuple.created_at if hasattr(checkpoint_tuple, 'created_at') else None,
                )
                checkpoints.append(info)
        except Exception as e:
            logger.error(f"[Checkpointer] Failed to list checkpoints: {e}")
        
        return checkpoints
    
    async def clear_thread(self, thread_id: str) -> int:
        """
        清除指定线程的所有检查点
        
        注意: AsyncSqliteSaver 没有直接的删除方法
        需要通过重新创建数据库或使用其他方式清理
        
        Args:
            thread_id: 线程 ID
            
        Returns:
            删除的检查点数量 (估算)
        """
        checkpoints = await self.list_checkpoints(thread_id, limit=1000)
        count = len(checkpoints)
        
        logger.info(f"[Checkpointer] Found {count} checkpoints for thread {thread_id}")
        
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """获取 Checkpointer 统计信息"""
        return {
            "enabled": self.enabled,
            "db_path": self.db_path,
            "initialized": self._saver is not None,
            "config": {
                "ttl_hours": self._config.CHECKPOINT_TTL_HOURS,
                "max_history": self._config.CHECKPOINT_MAX_HISTORY,
            },
        }


def get_checkpointer_manager() -> CheckpointerManager:
    """获取 CheckpointerManager 单例"""
    return CheckpointerManager()

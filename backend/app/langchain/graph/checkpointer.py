"""
LangGraph Checkpointer 模块

提供基于 SQLite 的状态持久化能力，支持:
1. 会话状态持久化
2. 断点恢复执行
3. 状态历史查询
4. 自动恢复机制
5. TTL 过期清理
6. 运行监控指标
"""
from typing import Optional, AsyncIterator, Dict, Any, List
from contextlib import asynccontextmanager, AsyncExitStack
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
import logging
import json
import asyncio

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.checkpoint.base import CheckpointTuple, Checkpoint
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from app.config import settings

logger = logging.getLogger(__name__)


MSGPACK_ALLOWED_MODULES = [
    ('app.knowledge_base.schemas', 'SearchResult'),
    ('app.knowledge_base.schemas', 'DocumentChunk'),
    ('app.knowledge_base.schemas', 'KnowledgeBase'),
    ('app.langchain.graph.state', 'SupervisorState'),
    ('app.langchain.graph.state', 'QueryIntent'),
    ('app.langchain.graph.state', 'RouteDecision'),
    ('app.langchain.graph.state', 'SourceReference'),
    ('app.langchain.graph.state', 'ToolCallRecord'),
]


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


@dataclass
class IncompleteExecution:
    """未完成的执行信息"""
    thread_id: str
    checkpoint_id: str
    next_nodes: List[str]
    created_at: Optional[datetime]
    state_values: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "checkpoint_id": self.checkpoint_id,
            "next_nodes": self.next_nodes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "state_values": {k: str(v)[:100] for k, v in self.state_values.items()},
        }


@dataclass
class CheckpointerMetrics:
    """Checkpointer 运行指标"""
    total_checkpoints: int = 0
    total_threads: int = 0
    db_size_bytes: int = 0
    oldest_checkpoint: Optional[datetime] = None
    newest_checkpoint: Optional[datetime] = None
    incomplete_executions: int = 0
    last_cleanup_time: Optional[datetime] = None
    cleanup_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_checkpoints": self.total_checkpoints,
            "total_threads": self.total_threads,
            "db_size_mb": round(self.db_size_bytes / (1024 * 1024), 2),
            "oldest_checkpoint": self.oldest_checkpoint.isoformat() if self.oldest_checkpoint else None,
            "newest_checkpoint": self.newest_checkpoint.isoformat() if self.newest_checkpoint else None,
            "incomplete_executions": self.incomplete_executions,
            "last_cleanup_time": self.last_cleanup_time.isoformat() if self.last_cleanup_time else None,
            "cleanup_count": self.cleanup_count,
        }


def create_serializer() -> JsonPlusSerializer:
    """
    创建带有允许列表的序列化器
    
    解决警告: "Deserializing unregistered type from checkpoint"
    """
    base_serializer = JsonPlusSerializer()
    return base_serializer.with_msgpack_allowlist(MSGPACK_ALLOWED_MODULES)


def _extract_timestamp_from_checkpoint(checkpoint_data: bytes) -> Optional[datetime]:
    """从 checkpoint blob 中提取时间戳"""
    try:
        import msgpack
        data = msgpack.unpackb(checkpoint_data, raw=False)
        ts = data.get('ts')
        if ts:
            return datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except Exception:
        pass
    return None


class CheckpointerManager:
    """
    Checkpointer 管理器
    
    负责:
    1. 创建和管理 AsyncSqliteSaver 实例
    2. 提供 checkpointer 生命周期管理
    3. 清理过期检查点 (TTL)
    4. 状态查询与恢复
    5. 自动恢复检测
    6. 运行监控指标
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
        self._conn: Optional[aiosqlite.Connection] = None
        self._exit_stack: Optional[AsyncExitStack] = None
        self._initialized = True
        self._metrics: CheckpointerMetrics = CheckpointerMetrics()
        self._cleanup_task: Optional[asyncio.Task] = None
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
        """获取或创建 AsyncSqliteSaver 实例"""
        if not self.enabled:
            logger.debug("[Checkpointer] Checkpointer is disabled")
            return None
        
        if self._saver is None:
            db_path = Path(self.db_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            self._exit_stack = AsyncExitStack()
            
            self._conn = await self._exit_stack.enter_async_context(
                aiosqlite.connect(str(db_path))
            )
            
            serializer = create_serializer()
            
            self._saver = AsyncSqliteSaver(conn=self._conn, serde=serializer)
            
            await self._saver.setup()
            
            await self._update_metrics()
            
            self._start_cleanup_task()
            
            logger.info(f"[Checkpointer] AsyncSqliteSaver initialized with db: {db_path}")
        
        return self._saver
    
    def _start_cleanup_task(self):
        """启动定时清理任务"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
            logger.info("[Checkpointer] Started periodic cleanup task")
    
    async def _periodic_cleanup(self):
        """定期清理过期检查点"""
        while True:
            try:
                await asyncio.sleep(3600)
                
                deleted = await self.cleanup_expired()
                if deleted > 0:
                    logger.info(f"[Checkpointer] Periodic cleanup: deleted {deleted} expired checkpoints")
                    self._metrics.last_cleanup_time = datetime.now(timezone.utc)
                    self._metrics.cleanup_count += 1
                    
            except asyncio.CancelledError:
                logger.info("[Checkpointer] Cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"[Checkpointer] Cleanup task error: {e}")
    
    async def close(self):
        """关闭 checkpointer 连接"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._saver = None
            self._conn = None
            logger.info("[Checkpointer] Closed")
    
    @asynccontextmanager
    async def get_checkpointer(self) -> AsyncIterator[Optional[AsyncSqliteSaver]]:
        """上下文管理器方式获取 checkpointer"""
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
        """获取指定的检查点"""
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
        """列出指定线程的检查点"""
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
                
                created_at = None
                if hasattr(checkpoint_tuple, 'created_at') and checkpoint_tuple.created_at:
                    created_at = checkpoint_tuple.created_at
                elif hasattr(checkpoint_tuple, 'checkpoint') and checkpoint_tuple.checkpoint:
                    created_at = _extract_timestamp_from_checkpoint(checkpoint_tuple.checkpoint)
                
                info = CheckpointInfo(
                    thread_id=thread_id,
                    checkpoint_id=configurable.get("checkpoint_id", ""),
                    checkpoint_ns=configurable.get("checkpoint_ns", ""),
                    parent_checkpoint_id=None,
                    metadata=checkpoint_tuple.metadata or {},
                    created_at=created_at,
                )
                checkpoints.append(info)
        except Exception as e:
            logger.error(f"[Checkpointer] Failed to list checkpoints: {e}")
        
        return checkpoints
    
    async def detect_incomplete_execution(
        self,
        thread_id: str,
    ) -> Optional[IncompleteExecution]:
        """检测未完成的执行"""
        saver = await self.get_saver()
        if not saver:
            return None
        
        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }
        
        try:
            state_snapshot = await saver.aget_tuple(config)
            
            if state_snapshot and hasattr(state_snapshot, 'pending') and state_snapshot.pending:
                pending_writes = state_snapshot.pending
                next_nodes = list(set([w[1] for w in pending_writes if len(w) > 1]))
                
                created_at = None
                if hasattr(state_snapshot, 'created_at') and state_snapshot.created_at:
                    created_at = state_snapshot.created_at
                elif hasattr(state_snapshot, 'checkpoint') and state_snapshot.checkpoint:
                    created_at = _extract_timestamp_from_checkpoint(state_snapshot.checkpoint)
                
                return IncompleteExecution(
                    thread_id=thread_id,
                    checkpoint_id=config.get("configurable", {}).get("checkpoint_id", ""),
                    next_nodes=next_nodes,
                    created_at=created_at,
                    state_values=state_snapshot.checkpoint.get('channel_values', {}) if state_snapshot.checkpoint else {},
                )
            
            if state_snapshot and hasattr(state_snapshot, 'checkpoint') and state_snapshot.checkpoint:
                channel_values = state_snapshot.checkpoint.get('channel_values', {})
                if channel_values.get('next') or channel_values.get('__pending__'):
                    created_at = _extract_timestamp_from_checkpoint(state_snapshot.checkpoint)
                    
                    return IncompleteExecution(
                        thread_id=thread_id,
                        checkpoint_id=config.get("configurable", {}).get("checkpoint_id", ""),
                        next_nodes=list(channel_values.get('next', [])),
                        created_at=created_at,
                        state_values=channel_values,
                    )
            
        except Exception as e:
            logger.debug(f"[Checkpointer] No incomplete execution found for {thread_id}: {e}")
        
        return None
    
    async def list_all_incomplete_executions(
        self,
        limit: int = 100,
    ) -> List[IncompleteExecution]:
        """列出所有未完成的执行"""
        incomplete = []
        
        try:
            if self._conn:
                async with self._conn.execute(
                    "SELECT DISTINCT thread_id FROM checkpoints LIMIT ?",
                    (limit,)
                ) as cursor:
                    async for row in cursor:
                        thread_id = row[0]
                        execution = await self.detect_incomplete_execution(thread_id)
                        if execution:
                            incomplete.append(execution)
        except Exception as e:
            logger.error(f"[Checkpointer] Failed to list incomplete executions: {e}")
        
        return incomplete
    
    async def clear_thread(self, thread_id: str) -> int:
        """清除指定线程的所有检查点"""
        if not self._conn:
            logger.warning("[Checkpointer] No connection available for clearing")
            return 0
        
        try:
            cursor = await self._conn.execute(
                "SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?",
                (thread_id,)
            )
            row = await cursor.fetchone()
            count = row[0] if row else 0
            
            await self._conn.execute(
                "DELETE FROM checkpoints WHERE thread_id = ?",
                (thread_id,)
            )
            await self._conn.commit()
            
            await self._conn.execute(
                "DELETE FROM writes WHERE thread_id = ?",
                (thread_id,)
            )
            await self._conn.commit()
            
            logger.info(f"[Checkpointer] Cleared {count} checkpoints for thread {thread_id}")
            
            await self._update_metrics()
            
            return count
            
        except Exception as e:
            logger.error(f"[Checkpointer] Failed to clear thread: {e}")
            return 0
    
    async def cleanup_expired(self) -> int:
        """清理过期的检查点"""
        if not self._conn:
            return 0
        
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self._config.CHECKPOINT_TTL_HOURS)
            
            cursor = await self._conn.execute(
                "SELECT thread_id, checkpoint FROM checkpoints"
            )
            rows = await cursor.fetchall()
            
            expired_threads = set()
            for row in rows:
                thread_id = row[0]
                checkpoint_data = row[1]
                timestamp = _extract_timestamp_from_checkpoint(checkpoint_data)
                
                if timestamp and timestamp < cutoff_time:
                    expired_threads.add(thread_id)
            
            total_deleted = 0
            for thread_id in expired_threads:
                count = await self.clear_thread(thread_id)
                total_deleted += count
            
            if total_deleted > 0:
                logger.info(f"[Checkpointer] Cleaned up {total_deleted} expired checkpoints (older than {cutoff_time.isoformat()})")
            
            await self._update_metrics()
            
            return total_deleted
            
        except Exception as e:
            logger.error(f"[Checkpointer] Failed to cleanup expired: {e}")
            return 0
    
    async def _update_metrics(self):
        """更新运行指标"""
        if not self._conn:
            return
        
        try:
            cursor = await self._conn.execute("SELECT COUNT(*) FROM checkpoints")
            row = await cursor.fetchone()
            self._metrics.total_checkpoints = row[0] if row else 0
            
            cursor = await self._conn.execute("SELECT COUNT(DISTINCT thread_id) FROM checkpoints")
            row = await cursor.fetchone()
            self._metrics.total_threads = row[0] if row else 0
            
            cursor = await self._conn.execute("SELECT checkpoint FROM checkpoints ORDER BY rowid ASC LIMIT 1")
            row = await cursor.fetchone()
            if row and row[0]:
                self._metrics.oldest_checkpoint = _extract_timestamp_from_checkpoint(row[0])
            
            cursor = await self._conn.execute("SELECT checkpoint FROM checkpoints ORDER BY rowid DESC LIMIT 1")
            row = await cursor.fetchone()
            if row and row[0]:
                self._metrics.newest_checkpoint = _extract_timestamp_from_checkpoint(row[0])
            
            db_path = Path(self.db_path)
            if db_path.exists():
                self._metrics.db_size_bytes = db_path.stat().st_size
            
            incomplete = await self.list_all_incomplete_executions(limit=1000)
            self._metrics.incomplete_executions = len(incomplete)
            
        except Exception as e:
            logger.error(f"[Checkpointer] Failed to update metrics: {e}")
    
    def get_metrics(self) -> CheckpointerMetrics:
        """获取 Checkpointer 运行指标"""
        return self._metrics
    
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
            "metrics": self._metrics.to_dict(),
        }


def get_checkpointer_manager() -> CheckpointerManager:
    """获取 CheckpointerManager 单例"""
    return CheckpointerManager()

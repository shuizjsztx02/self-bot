"""
Agent 实例管理器
实现 Agent 实例的缓存、生命周期管理和历史消息加载
"""
from typing import Dict, Optional
from datetime import datetime, timezone, timedelta
import asyncio
import logging

logger = logging.getLogger(__name__)


class AgentManager:
    """
    Agent 实例管理器
    
    职责:
    1. 缓存活跃会话的 Agent 实例
    2. 管理实例生命周期 (创建、获取、清理)
    3. 从数据库加载历史消息
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        from app.config import settings
        
        self._active_agents: Dict[str, any] = {}
        self._access_times: Dict[str, datetime] = {}
        self._ttl: int = getattr(settings, 'AGENT_CACHE_TTL', 3600)
        self._max_agents: int = getattr(settings, 'AGENT_CACHE_MAX_SIZE', 100)
        self._lock = asyncio.Lock()
        self._initialized = True
        
        logger.info(f"AgentManager initialized: ttl={self._ttl}s, max_agents={self._max_agents}")
    
    async def get_agent(
        self,
        conversation_id: str,
        db_session,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        获取或创建 Agent 实例
        
        Args:
            conversation_id: 会话 ID
            db_session: 数据库会话
            provider: LLM 提供商
            model: 模型名称
            
        Returns:
            SupervisorAgent 实例
        """
        async with self._lock:
            if conversation_id in self._active_agents:
                self._access_times[conversation_id] = datetime.now(timezone.utc)
                logger.debug(f"Agent cache hit: {conversation_id}")
                return self._active_agents[conversation_id]
            
            from app.langchain.agents.supervisor_agent import SupervisorAgent
            from app.config import settings
            
            agent = SupervisorAgent(
                provider=provider,
                model=model,
                conversation_id=conversation_id,
                db_session=db_session,
            )
            
            history_limit = getattr(settings, 'HISTORY_LOAD_LIMIT', 20)
            if getattr(settings, 'HISTORY_LOAD_ENABLED', True):
                try:
                    loaded_count = await agent.load_history(db_session, limit=history_limit)
                    logger.info(f"Loaded {loaded_count} history messages for conversation {conversation_id}")
                except Exception as e:
                    logger.warning(f"Failed to load history for {conversation_id}: {e}")
            
            self._active_agents[conversation_id] = agent
            self._access_times[conversation_id] = datetime.now(timezone.utc)
            
            logger.info(f"Agent created and cached: {conversation_id}, total cached: {len(self._active_agents)}")
            
            if len(self._active_agents) > self._max_agents:
                await self._evict_oldest()
            
            return agent
    
    async def remove_agent(self, conversation_id: str) -> bool:
        """
        移除缓存的 Agent 实例
        
        Args:
            conversation_id: 会话 ID
            
        Returns:
            是否成功移除
        """
        async with self._lock:
            if conversation_id in self._active_agents:
                del self._active_agents[conversation_id]
                del self._access_times[conversation_id]
                logger.info(f"Agent removed from cache: {conversation_id}")
                return True
            return False
    
    async def clear_expired(self) -> int:
        """
        清理过期的 Agent 实例
        
        Returns:
            清理的实例数量
        """
        async with self._lock:
            now = datetime.now(timezone.utc)
            expired_ids = [
                conv_id for conv_id, last_access in self._access_times.items()
                if (now - last_access).total_seconds() > self._ttl
            ]
            
            for conv_id in expired_ids:
                del self._active_agents[conv_id]
                del self._access_times[conv_id]
            
            if expired_ids:
                logger.info(f"Cleared {len(expired_ids)} expired agents")
            
            return len(expired_ids)
    
    async def _evict_oldest(self):
        """清理最久未访问的 Agent"""
        if not self._access_times:
            return
        
        sorted_ids = sorted(
            self._access_times.keys(),
            key=lambda x: self._access_times[x]
        )
        
        evict_count = max(1, len(sorted_ids) // 10)
        
        for conv_id in sorted_ids[:evict_count]:
            del self._active_agents[conv_id]
            del self._access_times[conv_id]
        
        logger.info(f"Evicted {evict_count} oldest agents, remaining: {len(self._active_agents)}")
    
    def get_stats(self) -> dict:
        """
        获取缓存统计信息
        
        Returns:
            统计信息字典
        """
        now = datetime.now(timezone.utc)
        
        agent_ages = {
            conv_id: (now - last_access).total_seconds()
            for conv_id, last_access in self._access_times.items()
        }
        
        return {
            "total_cached": len(self._active_agents),
            "max_agents": self._max_agents,
            "ttl_seconds": self._ttl,
            "agent_ages": agent_ages,
            "oldest_age": max(agent_ages.values()) if agent_ages else 0,
            "newest_age": min(agent_ages.values()) if agent_ages else 0,
        }
    
    def has_agent(self, conversation_id: str) -> bool:
        """检查是否存在缓存的 Agent"""
        return conversation_id in self._active_agents
    
    async def clear_all(self) -> int:
        """清空所有缓存的 Agent"""
        async with self._lock:
            count = len(self._active_agents)
            self._active_agents.clear()
            self._access_times.clear()
            logger.info(f"Cleared all {count} cached agents")
            return count


agent_manager = AgentManager()

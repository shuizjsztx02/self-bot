"""
流式中断管理器

用于管理流式输出的中断状态，支持用户主动中断LLM生成
"""

import asyncio
from typing import Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field


@dataclass
class StreamSession:
    session_id: str
    conversation_id: Optional[str] = None
    is_interrupted: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    interrupted_at: Optional[datetime] = None
    

class StreamInterruptManager:
    """
    流式中断管理器
    
    单例模式，管理所有活跃的流式会话
    """
    
    _instance = None
    _sessions: Dict[str, StreamSession] = {}
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> "StreamInterruptManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def create_session(
        self, 
        session_id: str, 
        conversation_id: Optional[str] = None
    ) -> StreamSession:
        async with self._lock:
            session = StreamSession(
                session_id=session_id,
                conversation_id=conversation_id,
            )
            self._sessions[session_id] = session
            return session
    
    async def get_session(self, session_id: str) -> Optional[StreamSession]:
        async with self._lock:
            return self._sessions.get(session_id)
    
    async def interrupt(self, session_id: str) -> bool:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.is_interrupted = True
                session.interrupted_at = datetime.now()
                return True
            return False
    
    async def is_interrupted(self, session_id: str) -> bool:
        async with self._lock:
            session = self._sessions.get(session_id)
            return session.is_interrupted if session else False
    
    async def remove_session(self, session_id: str) -> bool:
        async with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False
    
    async def cleanup_expired(self, max_age_minutes: int = 30) -> int:
        async with self._lock:
            now = datetime.now()
            expired = [
                sid for sid, session in self._sessions.items()
                if now - session.created_at > timedelta(minutes=max_age_minutes)
            ]
            for sid in expired:
                del self._sessions[sid]
            return len(expired)
    
    def get_active_sessions(self) -> list:
        return [
            {
                "session_id": s.session_id,
                "conversation_id": s.conversation_id,
                "is_interrupted": s.is_interrupted,
                "created_at": s.created_at.isoformat(),
            }
            for s in self._sessions.values()
        ]


class StreamInterruptedException(Exception):
    def __init__(self, message: str = "Stream was interrupted by user"):
        self.message = message
        super().__init__(self.message)


def get_stream_interrupt_manager() -> StreamInterruptManager:
    return StreamInterruptManager.get_instance()

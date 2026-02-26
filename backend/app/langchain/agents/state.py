"""
Agent 状态管理模块

用于追踪 Agent 执行状态、会话管理和状态持久化
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
import asyncio


class AgentStatus(str, Enum):
    """Agent 状态枚举"""
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    ERROR = "error"
    COMPLETED = "completed"


class AgentStep(BaseModel):
    """Agent 执行步骤"""
    step_id: str
    step_type: str  # "intent", "route", "tool_call", "tool_result", "llm_call", "response"
    agent_name: str
    timestamp: datetime = Field(default_factory=datetime.now)
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None


class AgentSession(BaseModel):
    """Agent 会话状态"""
    session_id: str
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    status: AgentStatus = AgentStatus.IDLE
    current_agent: Optional[str] = None
    steps: List[AgentStep] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def add_step(self, step: AgentStep):
        """添加执行步骤"""
        self.steps.append(step)
        self.updated_at = datetime.now()
    
    def get_last_step(self) -> Optional[AgentStep]:
        """获取最后一个步骤"""
        return self.steps[-1] if self.steps else None
    
    def get_steps_by_type(self, step_type: str) -> List[AgentStep]:
        """按类型获取步骤"""
        return [s for s in self.steps if s.step_type == step_type]


class AgentStateManager:
    """
    Agent 状态管理器
    
    功能：
    1. 会话创建和管理
    2. 状态追踪
    3. 执行历史记录
    """
    
    _instance = None
    _sessions: Dict[str, AgentSession] = {}
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def create_session(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> AgentSession:
        """创建新会话"""
        import uuid
        session_id = str(uuid.uuid4())
        
        session = AgentSession(
            session_id=session_id,
            conversation_id=conversation_id,
            user_id=user_id,
        )
        
        async with self._lock:
            self._sessions[session_id] = session
        
        return session
    
    async def get_session(self, session_id: str) -> Optional[AgentSession]:
        """获取会话"""
        return self._sessions.get(session_id)
    
    async def update_session_status(
        self,
        session_id: str,
        status: AgentStatus,
        current_agent: Optional[str] = None,
    ):
        """更新会话状态"""
        session = self._sessions.get(session_id)
        if session:
            session.status = status
            session.current_agent = current_agent
            session.updated_at = datetime.now()
    
    async def add_step(
        self,
        session_id: str,
        step: AgentStep,
    ):
        """添加执行步骤"""
        session = self._sessions.get(session_id)
        if session:
            session.add_step(step)
    
    async def end_session(self, session_id: str):
        """结束会话"""
        session = self._sessions.get(session_id)
        if session:
            session.status = AgentStatus.COMPLETED
            session.updated_at = datetime.now()
    
    async def cleanup_old_sessions(self, max_age_minutes: int = 60):
        """清理过期会话"""
        now = datetime.now()
        async with self._lock:
            to_remove = []
            for session_id, session in self._sessions.items():
                age = (now - session.updated_at).total_seconds() / 60
                if age > max_age_minutes:
                    to_remove.append(session_id)
            
            for session_id in to_remove:
                del self._sessions[session_id]
        
        return len(to_remove)
    
    def get_active_sessions(self) -> List[AgentSession]:
        """获取所有活跃会话"""
        return [
            s for s in self._sessions.values()
            if s.status in [AgentStatus.RUNNING, AgentStatus.WAITING]
        ]
    
    def get_session_count(self) -> int:
        """获取会话数量"""
        return len(self._sessions)


def get_state_manager() -> AgentStateManager:
    """获取状态管理器实例"""
    return AgentStateManager()

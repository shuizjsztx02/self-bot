"""
执行追踪模块

用于持久化 Agent 执行追踪数据，支持性能监控和调试
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, Field
import json
import asyncio


class TraceEvent(BaseModel):
    """追踪事件"""
    event_id: str
    event_type: str  # "llm_start", "llm_end", "tool_start", "tool_end", "chain_start", "chain_end", "error"
    timestamp: datetime = Field(default_factory=datetime.now)
    name: str
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionTrace(BaseModel):
    """执行追踪记录"""
    trace_id: str
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    query: Optional[str] = None
    response: Optional[str] = None
    events: List[TraceEvent] = Field(default_factory=list)
    total_duration_ms: Optional[float] = None
    token_usage: Dict[str, int] = Field(default_factory=dict)
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    status: str = "running"  # "running", "completed", "error"
    
    def add_event(self, event: TraceEvent):
        """添加事件"""
        self.events.append(event)
    
    def calculate_total_duration(self):
        """计算总耗时"""
        if self.events:
            start = self.events[0].timestamp
            end = self.events[-1].timestamp
            self.total_duration_ms = (end - start).total_seconds() * 1000
        return self.total_duration_ms
    
    def get_summary(self) -> Dict[str, Any]:
        """获取摘要"""
        return {
            "trace_id": self.trace_id,
            "conversation_id": self.conversation_id,
            "query": self.query[:100] if self.query else None,
            "response": self.response[:100] if self.response else None,
            "total_duration_ms": self.total_duration_ms,
            "token_usage": self.token_usage,
            "tool_calls_count": len(self.tool_calls),
            "events_count": len(self.events),
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


class TraceStorage:
    """追踪存储"""
    
    def __init__(self, storage_path: str = "./data/traces"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    async def save_trace(self, trace: ExecutionTrace):
        """保存追踪记录"""
        trace_file = self.storage_path / f"{trace.trace_id}.json"
        
        trace_data = trace.model_dump()
        trace_data["created_at"] = trace.created_at.isoformat()
        for event in trace_data["events"]:
            event["timestamp"] = event["timestamp"].isoformat()
        
        import aiofiles
        async with aiofiles.open(trace_file, "w", encoding="utf-8") as f:
            await f.write(json.dumps(trace_data, ensure_ascii=False, indent=2))
    
    async def load_trace(self, trace_id: str) -> Optional[ExecutionTrace]:
        """加载追踪记录"""
        trace_file = self.storage_path / f"{trace_id}.json"
        
        if not trace_file.exists():
            return None
        
        import aiofiles
        async with aiofiles.open(trace_file, "r", encoding="utf-8") as f:
            data = json.loads(await f.read())
        
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        for event in data["events"]:
            event["timestamp"] = datetime.fromisoformat(event["timestamp"])
        
        return ExecutionTrace(**data)
    
    async def list_traces(self, limit: int = 100) -> List[Dict[str, Any]]:
        """列出追踪记录"""
        traces = []
        
        for trace_file in sorted(
            self.storage_path.glob("*.json"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )[:limit]:
            try:
                import aiofiles
                async with aiofiles.open(trace_file, "r", encoding="utf-8") as f:
                    data = json.loads(await f.read())
                traces.append({
                    "trace_id": data["trace_id"],
                    "conversation_id": data.get("conversation_id"),
                    "query": data.get("query", "")[:100],
                    "status": data.get("status"),
                    "created_at": data.get("created_at"),
                })
            except:
                continue
        
        return traces


class ExecutionTracer:
    """
    执行追踪器
    
    功能：
    1. 记录 Agent 执行过程
    2. 持久化追踪数据
    3. 性能分析
    """
    
    _instance = None
    _traces: Dict[str, ExecutionTrace] = {}
    _storage: Optional[TraceStorage] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._storage is None:
            self._storage = TraceStorage()
    
    def start_trace(
        self,
        conversation_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        query: Optional[str] = None,
    ) -> ExecutionTrace:
        """开始追踪"""
        import uuid
        trace_id = str(uuid.uuid4())
        
        trace = ExecutionTrace(
            trace_id=trace_id,
            conversation_id=conversation_id,
            session_id=session_id,
            user_id=user_id,
            query=query,
        )
        
        self._traces[trace_id] = trace
        return trace
    
    def add_event(
        self,
        trace_id: str,
        event_type: str,
        name: str,
        input_data: Optional[Dict] = None,
        output_data: Optional[Dict] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> TraceEvent:
        """添加事件"""
        import uuid
        
        trace = self._traces.get(trace_id)
        if not trace:
            raise ValueError(f"Trace {trace_id} not found")
        
        event = TraceEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            name=name,
            input_data=input_data,
            output_data=output_data,
            error=error,
            metadata=metadata or {},
        )
        
        trace.add_event(event)
        
        if event_type == "error":
            trace.status = "error"
        
        return event
    
    def end_trace(
        self,
        trace_id: str,
        response: Optional[str] = None,
        token_usage: Optional[Dict] = None,
    ):
        """结束追踪"""
        trace = self._traces.get(trace_id)
        if not trace:
            return
        
        trace.response = response
        trace.status = "completed"
        trace.calculate_total_duration()
        
        if token_usage:
            trace.token_usage = token_usage
        
        for event in trace.events:
            if event.event_type == "tool_start":
                trace.tool_calls.append({
                    "name": event.name,
                    "input": event.input_data,
                })
    
    async def save_trace(self, trace_id: str):
        """保存追踪记录"""
        trace = self._traces.get(trace_id)
        if trace and self._storage:
            await self._storage.save_trace(trace)
    
    def get_trace(self, trace_id: str) -> Optional[ExecutionTrace]:
        """获取追踪记录"""
        return self._traces.get(trace_id)
    
    async def get_trace_from_storage(self, trace_id: str) -> Optional[ExecutionTrace]:
        """从存储加载追踪记录"""
        return await self._storage.load_trace(trace_id)
    
    async def list_traces(self, limit: int = 100) -> List[Dict[str, Any]]:
        """列出追踪记录"""
        if self._storage:
            return await self._storage.list_traces(limit)
        return []
    
    def get_active_traces(self) -> List[ExecutionTrace]:
        """获取活跃追踪"""
        return [
            t for t in self._traces.values()
            if t.status == "running"
        ]
    
    def get_performance_stats(self, trace_id: str) -> Dict[str, Any]:
        """获取性能统计"""
        trace = self._traces.get(trace_id)
        if not trace:
            return {}
        
        stats = {
            "total_duration_ms": trace.total_duration_ms,
            "events_count": len(trace.events),
            "tool_calls_count": len(trace.tool_calls),
            "token_usage": trace.token_usage,
            "events_by_type": {},
        }
        
        for event in trace.events:
            if event.event_type not in stats["events_by_type"]:
                stats["events_by_type"][event.event_type] = 0
            stats["events_by_type"][event.event_type] += 1
        
        return stats


def get_tracer() -> ExecutionTracer:
    """获取追踪器实例"""
    return ExecutionTracer()

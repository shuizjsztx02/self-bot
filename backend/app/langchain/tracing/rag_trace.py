"""
RAG 链路追踪工具

用于跟踪和记录 RAG 请求的完整执行链路
"""
import logging
import time
import uuid
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from contextvars import ContextVar
import json

logger = logging.getLogger(__name__)

_trace_context: ContextVar[Optional["RagTraceContext"]] = ContextVar("rag_trace", default=None)


@dataclass
class TraceStep:
    """追踪步骤"""
    step_id: str
    step_name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str = "running"
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    children: List["TraceStep"] = field(default_factory=list)
    
    def finish(self, output_data: Dict[str, Any] = None, error: str = None):
        """完成步骤"""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        if output_data:
            self.output_data = output_data
        if error:
            self.error = error
            self.status = "error"
        else:
            self.status = "completed"


@dataclass
class RagTraceContext:
    """RAG 链路追踪上下文"""
    trace_id: str
    query: str
    start_time: float
    steps: List[TraceStep] = field(default_factory=list)
    current_step: Optional[TraceStep] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def start_step(self, step_name: str, input_data: Dict[str, Any] = None) -> TraceStep:
        """开始一个新步骤"""
        step = TraceStep(
            step_id=f"{self.trace_id}_{len(self.steps)}",
            step_name=step_name,
            start_time=time.time(),
            input_data=input_data or {},
        )
        self.steps.append(step)
        self.current_step = step
        
        _log_step_start(self.trace_id, step_name, input_data)
        return step
    
    def finish_step(self, output_data: Dict[str, Any] = None, error: str = None):
        """完成当前步骤"""
        if self.current_step:
            self.current_step.finish(output_data, error)
            _log_step_end(
                self.trace_id,
                self.current_step.step_name,
                self.current_step.duration_ms,
                output_data,
                error
            )
            self.current_step = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "trace_id": self.trace_id,
            "query": self.query,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "total_duration_ms": (time.time() - self.start_time) * 1000,
            "steps": [
                {
                    "step_name": s.step_name,
                    "duration_ms": s.duration_ms,
                    "status": s.status,
                    "input": _truncate_dict(s.input_data),
                    "output": _truncate_dict(s.output_data),
                    "error": s.error,
                }
                for s in self.steps
            ],
            "metadata": self.metadata,
        }


def _truncate_dict(d: Dict, max_len: int = 200) -> Dict:
    """截断字典值用于日志显示"""
    result = {}
    for k, v in d.items():
        if isinstance(v, str) and len(v) > max_len:
            result[k] = v[:max_len] + "..."
        elif isinstance(v, dict):
            result[k] = _truncate_dict(v, max_len)
        elif isinstance(v, list):
            result[k] = f"[{len(v)} items]"
        else:
            result[k] = v
    return result


def _log_step_start(trace_id: str, step_name: str, input_data: Dict = None):
    """记录步骤开始日志"""
    input_str = json.dumps(_truncate_dict(input_data or {}), ensure_ascii=False)
    logger.info(f"[Trace:{trace_id[:8]}] ▶ START: {step_name} | input: {input_str}")


def _log_step_end(trace_id: str, step_name: str, duration_ms: float, output_data: Dict = None, error: str = None):
    """记录步骤结束日志"""
    output_str = json.dumps(_truncate_dict(output_data or {}), ensure_ascii=False)
    if error:
        logger.error(f"[Trace:{trace_id[:8]}] ✗ END: {step_name} | {duration_ms:.1f}ms | error: {error}")
    else:
        logger.info(f"[Trace:{trace_id[:8]}] ✓ END: {step_name} | {duration_ms:.1f}ms | output: {output_str}")


def start_rag_trace(query: str, metadata: Dict[str, Any] = None) -> RagTraceContext:
    """开始 RAG 链路追踪"""
    trace_id = str(uuid.uuid4())
    ctx = RagTraceContext(
        trace_id=trace_id,
        query=query,
        start_time=time.time(),
        metadata=metadata or {},
    )
    _trace_context.set(ctx)
    
    logger.info(f"[Trace:{trace_id[:8]}] 🚀 START RAG TRACE | query: {query}")
    return ctx


def get_rag_trace() -> Optional[RagTraceContext]:
    """获取当前 RAG 链路追踪上下文"""
    return _trace_context.get()


def end_rag_trace(output: str = None, error: str = None) -> Optional[Dict[str, Any]]:
    """结束 RAG 链路追踪"""
    ctx = _trace_context.get()
    if not ctx:
        return None
    
    total_duration = (time.time() - ctx.start_time) * 1000
    
    if error:
        logger.error(f"[Trace:{ctx.trace_id[:8]}] 💥 TRACE FAILED | {total_duration:.1f}ms | error: {error}")
    else:
        logger.info(f"[Trace:{ctx.trace_id[:8]}] 🏁 TRACE COMPLETE | {total_duration:.1f}ms | output: {(output or '')[:100]}...")
    
    result = ctx.to_dict()
    _trace_context.set(None)
    return result


class RagTraceStep:
    """RAG 追踪步骤上下文管理器"""
    
    def __init__(self, step_name: str, input_data: Dict[str, Any] = None):
        self.step_name = step_name
        self.input_data = input_data or {}
        self.ctx = get_rag_trace()
        self.step = None
    
    def __enter__(self):
        if self.ctx:
            self.step = self.ctx.start_step(self.step_name, self.input_data)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.ctx:
            error = str(exc_val) if exc_val else None
            self.ctx.finish_step(error=error)
        return False
    
    def finish(self, output_data: Dict[str, Any] = None):
        """手动完成步骤"""
        if self.ctx and self.step:
            self.ctx.finish_step(output_data)


def trace_step(step_name: str, input_data: Dict[str, Any] = None):
    """追踪步骤装饰器/上下文管理器"""
    return RagTraceStep(step_name, input_data)

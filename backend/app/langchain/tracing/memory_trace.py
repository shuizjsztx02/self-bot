"""
记忆系统链路追踪工具

用于跟踪和记录记忆系统操作的完整执行链路
包括：短期记忆、长期记忆、摘要生成、向量存储等
"""
import logging
import time
import uuid
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from contextvars import ContextVar
from contextlib import contextmanager
import json

logger = logging.getLogger(__name__)

_current_trace: Optional["MemoryTraceContext"] = None


def get_memory_trace() -> Optional["MemoryTraceContext"]:
    """获取当前记忆系统链路追踪上下文"""
    global _current_trace
    return _current_trace


def _set_memory_trace(ctx: Optional["MemoryTraceContext"]):
    """设置当前记忆系统链路追踪上下文"""
    global _current_trace
    _current_trace = ctx


@dataclass
class MemoryTraceStep:
    """记忆追踪步骤"""
    step_id: str
    step_name: str
    step_type: str  # short_term, long_term, summary, vector
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str = "running"
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
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
class MemoryTraceContext:
    """记忆系统链路追踪上下文"""
    trace_id: str
    operation: str  # store, retrieve, summarize, finalize, chat
    start_time: float
    steps: List[MemoryTraceStep] = field(default_factory=list)
    current_step: Optional[MemoryTraceStep] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def start_step(
        self, 
        step_name: str, 
        step_type: str = "general",
        input_data: Dict[str, Any] = None
    ) -> MemoryTraceStep:
        """开始一个新步骤"""
        step = MemoryTraceStep(
            step_id=f"{self.trace_id}_{len(self.steps)}",
            step_name=step_name,
            step_type=step_type,
            start_time=time.time(),
            input_data=input_data or {},
        )
        self.steps.append(step)
        self.current_step = step
        
        _log_memory_step_start(self.trace_id, step_name, step_type, input_data)
        return step
    
    def finish_step(self, output_data: Dict[str, Any] = None, error: str = None):
        """完成当前步骤"""
        if self.current_step:
            self.current_step.finish(output_data, error)
            _log_memory_step_end(
                self.trace_id,
                self.current_step.step_name,
                self.current_step.step_type,
                self.current_step.duration_ms,
                output_data,
                error
            )
            self.current_step = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "trace_id": self.trace_id,
            "operation": self.operation,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "total_duration_ms": (time.time() - self.start_time) * 1000,
            "steps": [
                {
                    "step_name": s.step_name,
                    "step_type": s.step_type,
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


def _log_memory_step_start(trace_id: str, step_name: str, step_type: str, input_data: Dict = None):
    """记录步骤开始日志"""
    input_str = json.dumps(_truncate_dict(input_data or {}), ensure_ascii=False)
    logger.info(f"[Memory:{trace_id[:8]}] ▶ START [{step_type}] {step_name} | input: {input_str}")


def _log_memory_step_end(
    trace_id: str, 
    step_name: str, 
    step_type: str,
    duration_ms: float, 
    output_data: Dict = None, 
    error: str = None
):
    """记录步骤结束日志"""
    output_str = json.dumps(_truncate_dict(output_data or {}), ensure_ascii=False)
    if error:
        logger.error(f"[Memory:{trace_id[:8]}] ✗ END [{step_type}] {step_name} | {duration_ms:.1f}ms | error: {error}")
    else:
        logger.info(f"[Memory:{trace_id[:8]}] ✓ END [{step_type}] {step_name} | {duration_ms:.1f}ms | output: {output_str}")


def start_memory_trace(operation: str, metadata: Dict[str, Any] = None) -> MemoryTraceContext:
    """
    开始记忆系统链路追踪
    
    Args:
        operation: 操作类型 (store, retrieve, summarize, finalize, chat)
        metadata: 额外元数据
    
    Returns:
        MemoryTraceContext: 追踪上下文
    """
    trace_id = str(uuid.uuid4())
    ctx = MemoryTraceContext(
        trace_id=trace_id,
        operation=operation,
        start_time=time.time(),
        metadata=metadata or {},
    )
    _set_memory_trace(ctx)
    
    logger.info(f"[Memory:{trace_id[:8]}] 🚀 START MEMORY TRACE | operation: {operation}")
    return ctx


def get_memory_trace() -> Optional[MemoryTraceContext]:
    """获取当前记忆系统链路追踪上下文"""
    return _current_trace


def end_memory_trace(output: str = None, error: str = None) -> Optional[Dict[str, Any]]:
    """
    结束记忆系统链路追踪
    
    Args:
        output: 输出摘要
        error: 错误信息
    
    Returns:
        追踪结果字典
    """
    ctx = get_memory_trace()
    if not ctx:
        return None
    
    total_duration = (time.time() - ctx.start_time) * 1000
    
    if error:
        logger.error(f"[Memory:{ctx.trace_id[:8]}] 💥 TRACE FAILED | {total_duration:.1f}ms | error: {error}")
    else:
        logger.info(f"[Memory:{ctx.trace_id[:8]}] 🏁 TRACE COMPLETE | {total_duration:.1f}ms | output: {(output or '')[:100]}...")
    
    result = ctx.to_dict()
    _set_memory_trace(None)
    return result


class MemoryTraceStepContext:
    """记忆追踪步骤上下文管理器"""
    
    def __init__(self, step_name: str, step_type: str = "general", input_data: Dict[str, Any] = None):
        self.step_name = step_name
        self.step_type = step_type
        self.input_data = input_data or {}
        self.ctx = None
        self.step = None
    
    def __enter__(self):
        self.ctx = get_memory_trace()
        if self.ctx:
            self.step = self.ctx.start_step(self.step_name, self.step_type, self.input_data)
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


@contextmanager
def memory_trace_step(step_name: str, step_type: str = "general", input_data: Dict[str, Any] = None):
    """记忆追踪步骤上下文管理器"""
    step_ctx = MemoryTraceStepContext(step_name, step_type, input_data)
    try:
        yield step_ctx
    except Exception as e:
        if step_ctx.ctx:
            step_ctx.ctx.finish_step(error=str(e))
        raise
    else:
        if step_ctx.ctx and step_ctx.step:
            step_ctx.ctx.finish_step(step_ctx.step.output_data)


def trace_memory_step(step_name: str, step_type: str = "general", input_data: Dict[str, Any] = None):
    """追踪步骤装饰器/上下文管理器"""
    return MemoryTraceStepContext(step_name, step_type, input_data)


class MemoryTraceConfig:
    """记忆追踪配置"""
    
    def __init__(self):
        self.enabled: bool = True
        self.log_level: str = "INFO"
        self.max_content_length: int = 200
        self.trace_short_term: bool = True
        self.trace_long_term: bool = True
        self.trace_summary: bool = True
        self.trace_vector: bool = True
    
    def configure(
        self,
        enabled: bool = True,
        log_level: str = "INFO",
        max_content_length: int = 200,
        trace_short_term: bool = True,
        trace_long_term: bool = True,
        trace_summary: bool = True,
        trace_vector: bool = True,
    ):
        """配置追踪器"""
        self.enabled = enabled
        self.log_level = log_level
        self.max_content_length = max_content_length
        self.trace_short_term = trace_short_term
        self.trace_long_term = trace_long_term
        self.trace_summary = trace_summary
        self.trace_vector = trace_vector
    
    def should_trace(self, step_type: str) -> bool:
        """检查是否应该追踪指定类型的步骤"""
        if not self.enabled:
            return False
        
        type_mapping = {
            "short_term": self.trace_short_term,
            "long_term": self.trace_long_term,
            "summary": self.trace_summary,
            "vector": self.trace_vector,
            "general": True,
        }
        return type_mapping.get(step_type, True)


memory_trace_config = MemoryTraceConfig()


def configure_memory_trace(
    enabled: bool = True,
    log_level: str = "INFO",
    max_content_length: int = 200,
    trace_short_term: bool = True,
    trace_long_term: bool = True,
    trace_summary: bool = True,
    trace_vector: bool = True,
):
    """配置记忆追踪器"""
    memory_trace_config.configure(
        enabled=enabled,
        log_level=log_level,
        max_content_length=max_content_length,
        trace_short_term=trace_short_term,
        trace_long_term=trace_long_term,
        trace_summary=trace_summary,
        trace_vector=trace_vector,
    )

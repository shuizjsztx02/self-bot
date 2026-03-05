"""
统一追踪系统

整合并兼容以下追踪模块：
1. graph/tracer.py - GraphTracer
2. tracing/rag_trace.py - RagTraceContext
3. tracing/memory_trace.py - MemoryTraceContext
4. tracing/execution.py - ExecutionTracer

确保日志格式与现有实现完全一致
"""
import time
import logging
import uuid
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from contextvars import ContextVar
from contextlib import contextmanager

logger = logging.getLogger(__name__)

_trace_context: ContextVar[Optional["UnifiedTraceContext"]] = ContextVar("unified_trace", default=None)


@dataclass
class TraceStep:
    """追踪步骤 - 兼容 RagTraceContext.TraceStep 和 MemoryTraceStep"""
    step_id: str
    step_name: str
    step_type: str = "general"
    start_time: float = field(default_factory=time.time)
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
class UnifiedTraceContext:
    """
    统一追踪上下文
    
    兼容以下格式：
    - RagTraceContext (RAG 追踪)
    - MemoryTraceContext (记忆追踪)
    - GraphTrace (图追踪)
    - ExecutionTrace (执行追踪)
    """
    trace_id: str
    trace_type: str
    query: str = ""
    operation: str = ""
    start_time: float = field(default_factory=time.time)
    steps: List[TraceStep] = field(default_factory=list)
    current_step: Optional[TraceStep] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def start_step(
        self, 
        step_name: str, 
        step_type: str = "general",
        input_data: Dict[str, Any] = None
    ) -> TraceStep:
        """开始一个新步骤"""
        step = TraceStep(
            step_id=f"{self.trace_id}_{len(self.steps)}",
            step_name=step_name,
            step_type=step_type,
            start_time=time.time(),
            input_data=input_data or {},
        )
        self.steps.append(step)
        self.current_step = step
        
        _log_step_start(self.trace_id, step_name, step_type, input_data)
        return step
    
    def finish_step(self, output_data: Dict[str, Any] = None, error: str = None):
        """完成当前步骤"""
        if self.current_step:
            self.current_step.finish(output_data, error)
            _log_step_end(
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
            "trace_type": self.trace_type,
            "query": self.query,
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
    
    def to_rag_trace_format(self) -> Dict[str, Any]:
        """转换为 RagTraceContext 格式"""
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
    
    def to_memory_trace_format(self) -> Dict[str, Any]:
        """转换为 MemoryTraceContext 格式"""
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
    """截断字典值用于日志显示 - 与原实现完全一致"""
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


def _log_step_start(trace_id: str, step_name: str, step_type: str, input_data: Dict = None):
    """
    记录步骤开始日志
    
    格式与原实现完全一致：
    - RAG: [Trace:xxx] ▶ START: step_name | input: {...}
    - Memory: [Memory:xxx] ▶ START [type] step_name | input: {...}
    - Skill: [Skill:xxx] ▶ START step_name | input: {...}
    """
    input_str = json.dumps(_truncate_dict(input_data or {}), ensure_ascii=False)
    trace_id_short = trace_id[:8]
    
    if step_type == "rag" or step_type == "general":
        logger.info(f"[Trace:{trace_id_short}] ▶ START: {step_name} | input: {input_str}")
    elif step_type in ["short_term", "long_term", "summary", "vector"]:
        logger.info(f"[Memory:{trace_id_short}] ▶ START [{step_type}] {step_name} | input: {input_str}")
    elif step_type == "skill":
        logger.info(f"[Skill:{trace_id_short}] ▶ START {step_name} | input: {input_str}")
    else:
        logger.info(f"[{step_type.upper()}:{trace_id_short}] ▶ START: {step_name} | input: {input_str}")


def _log_step_end(
    trace_id: str, 
    step_name: str, 
    step_type: str,
    duration_ms: float, 
    output_data: Dict = None, 
    error: str = None
):
    """
    记录步骤结束日志
    
    格式与原实现完全一致：
    - RAG: [Trace:xxx] ✓ END: step_name | 123.4ms | output: {...}
    - Memory: [Memory:xxx] ✓ END [type] step_name | 123.4ms | output: {...}
    """
    output_str = json.dumps(_truncate_dict(output_data or {}), ensure_ascii=False)
    trace_id_short = trace_id[:8]
    
    if error:
        if step_type == "rag" or step_type == "general":
            logger.error(f"[Trace:{trace_id_short}] ✗ END: {step_name} | {duration_ms:.1f}ms | error: {error}")
        elif step_type in ["short_term", "long_term", "summary", "vector"]:
            logger.error(f"[Memory:{trace_id_short}] ✗ END [{step_type}] {step_name} | {duration_ms:.1f}ms | error: {error}")
        else:
            logger.error(f"[{step_type.upper()}:{trace_id_short}] ✗ END: {step_name} | {duration_ms:.1f}ms | error: {error}")
    else:
        if step_type == "rag" or step_type == "general":
            logger.info(f"[Trace:{trace_id_short}] ✓ END: {step_name} | {duration_ms:.1f}ms | output: {output_str}")
        elif step_type in ["short_term", "long_term", "summary", "vector"]:
            logger.info(f"[Memory:{trace_id_short}] ✓ END [{step_type}] {step_name} | {duration_ms:.1f}ms | output: {output_str}")
        else:
            logger.info(f"[{step_type.upper()}:{trace_id_short}] ✓ END: {step_name} | {duration_ms:.1f}ms | output: {output_str}")


def start_rag_trace(query: str, metadata: Dict[str, Any] = None) -> UnifiedTraceContext:
    """
    开始 RAG 链路追踪
    
    兼容 rag_trace.py 的 start_rag_trace 函数
    """
    trace_id = str(uuid.uuid4())
    ctx = UnifiedTraceContext(
        trace_id=trace_id,
        trace_type="rag",
        query=query,
        metadata=metadata or {},
    )
    _trace_context.set(ctx)
    
    logger.info(f"[Trace:{trace_id[:8]}] 🚀 START RAG TRACE | query: {query}")
    return ctx


def start_memory_trace(operation: str, metadata: Dict[str, Any] = None) -> UnifiedTraceContext:
    """
    开始记忆系统链路追踪
    
    兼容 memory_trace.py 的 start_memory_trace 函数
    """
    trace_id = str(uuid.uuid4())
    ctx = UnifiedTraceContext(
        trace_id=trace_id,
        trace_type="memory",
        operation=operation,
        metadata=metadata or {},
    )
    _trace_context.set(ctx)
    
    logger.info(f"[Memory:{trace_id[:8]}] 🚀 START MEMORY TRACE | operation: {operation}")
    return ctx


def start_skill_trace(skill_name: str, metadata: Dict[str, Any] = None) -> UnifiedTraceContext:
    """开始技能追踪"""
    trace_id = str(uuid.uuid4())
    ctx = UnifiedTraceContext(
        trace_id=trace_id,
        trace_type="skill",
        query=skill_name,
        metadata=metadata or {},
    )
    _trace_context.set(ctx)
    
    logger.info(f"[Skill:{trace_id[:8]}] 🚀 START SKILL TRACE | skill: {skill_name}")
    return ctx


def start_chat_trace(conversation_id: str, metadata: Dict[str, Any] = None) -> UnifiedTraceContext:
    """开始对话追踪"""
    trace_id = str(uuid.uuid4())
    ctx = UnifiedTraceContext(
        trace_id=trace_id,
        trace_type="chat",
        query=conversation_id,
        metadata=metadata or {},
    )
    _trace_context.set(ctx)
    
    logger.info(f"[Chat:{trace_id[:8]}] 🚀 START CHAT TRACE | conversation: {conversation_id}")
    return ctx


def start_search_trace(query: str, metadata: Dict[str, Any] = None) -> UnifiedTraceContext:
    """开始搜索追踪"""
    trace_id = str(uuid.uuid4())
    ctx = UnifiedTraceContext(
        trace_id=trace_id,
        trace_type="search",
        query=query,
        metadata=metadata or {},
    )
    _trace_context.set(ctx)
    
    logger.info(f"[Search:{trace_id[:8]}] 🚀 START SEARCH TRACE | query: {query}")
    return ctx


def get_trace() -> Optional[UnifiedTraceContext]:
    """获取当前追踪上下文"""
    return _trace_context.get()


def get_rag_trace() -> Optional[UnifiedTraceContext]:
    """兼容 rag_trace.py 的 get_rag_trace 函数"""
    return _trace_context.get()


def get_memory_trace() -> Optional[UnifiedTraceContext]:
    """兼容 memory_trace.py 的 get_memory_trace 函数"""
    return _trace_context.get()


def end_rag_trace(output: str = None, error: str = None) -> Optional[Dict[str, Any]]:
    """
    结束 RAG 链路追踪
    
    兼容 rag_trace.py 的 end_rag_trace 函数
    """
    ctx = _trace_context.get()
    if not ctx:
        return None
    
    total_duration = (time.time() - ctx.start_time) * 1000
    
    if error:
        logger.error(f"[Trace:{ctx.trace_id[:8]}] 💥 TRACE FAILED | {total_duration:.1f}ms | error: {error}")
    else:
        logger.info(f"[Trace:{ctx.trace_id[:8]}] 🏁 TRACE COMPLETE | {total_duration:.1f}ms | output: {(output or '')[:100]}...")
    
    result = ctx.to_rag_trace_format()
    _trace_context.set(None)
    return result


def end_memory_trace(output: str = None, error: str = None) -> Optional[Dict[str, Any]]:
    """
    结束记忆系统链路追踪
    
    兼容 memory_trace.py 的 end_memory_trace 函数
    """
    ctx = _trace_context.get()
    if not ctx:
        return None
    
    total_duration = (time.time() - ctx.start_time) * 1000
    
    if error:
        logger.error(f"[Memory:{ctx.trace_id[:8]}] 💥 TRACE FAILED | {total_duration:.1f}ms | error: {error}")
    else:
        logger.info(f"[Memory:{ctx.trace_id[:8]}] 🏁 TRACE COMPLETE | {total_duration:.1f}ms | output: {(output or '')[:100]}...")
    
    result = ctx.to_memory_trace_format()
    _trace_context.set(None)
    return result


def end_skill_trace(output: str = None, error: str = None) -> Optional[Dict[str, Any]]:
    """结束技能追踪"""
    ctx = _trace_context.get()
    if not ctx:
        return None
    
    total_duration = (time.time() - ctx.start_time) * 1000
    
    if error:
        logger.error(f"[Skill:{ctx.trace_id[:8]}] 💥 TRACE FAILED | {total_duration:.1f}ms | error: {error}")
    else:
        logger.info(f"[Skill:{ctx.trace_id[:8]}] 🏁 TRACE COMPLETE | {total_duration:.1f}ms | output: {(output or '')[:100]}...")
    
    result = ctx.to_dict()
    _trace_context.set(None)
    return result


def end_trace(output: str = None, error: str = None) -> Optional[Dict[str, Any]]:
    """结束当前追踪（通用方法）"""
    ctx = _trace_context.get()
    if not ctx:
        return None
    
    if ctx.trace_type == "rag":
        return end_rag_trace(output, error)
    elif ctx.trace_type == "memory":
        return end_memory_trace(output, error)
    elif ctx.trace_type == "skill":
        return end_skill_trace(output, error)
    elif ctx.trace_type == "search":
        return end_search_trace(output, error)
    else:
        return end_chat_trace(output, error)


def end_search_trace(output: str = None, error: str = None) -> Optional[Dict[str, Any]]:
    """结束搜索追踪"""
    ctx = _trace_context.get()
    if not ctx:
        return None
    
    total_duration = (time.time() - ctx.start_time) * 1000
    
    if error:
        logger.error(f"[Search:{ctx.trace_id[:8]}] 💥 TRACE FAILED | {total_duration:.1f}ms | error: {error}")
    else:
        logger.info(f"[Search:{ctx.trace_id[:8]}] 🏁 TRACE COMPLETE | {total_duration:.1f}ms | output: {(output or '')[:100]}...")
    
    result = ctx.to_dict()
    _trace_context.set(None)
    return result


def end_chat_trace(output: str = None, error: str = None) -> Optional[Dict[str, Any]]:
    """结束对话追踪"""
    ctx = _trace_context.get()
    if not ctx:
        return None
    
    total_duration = (time.time() - ctx.start_time) * 1000
    
    if error:
        logger.error(f"[Chat:{ctx.trace_id[:8]}] 💥 TRACE FAILED | {total_duration:.1f}ms | error: {error}")
    else:
        logger.info(f"[Chat:{ctx.trace_id[:8]}] 🏁 TRACE COMPLETE | {total_duration:.1f}ms | output: {(output or '')[:100]}...")
    
    result = ctx.to_dict()
    _trace_context.set(None)
    return result


class TraceStepContext:
    """
    追踪步骤上下文管理器
    
    兼容 RagTraceStep 和 MemoryTraceStepContext
    """
    
    def __init__(
        self, 
        step_name: str, 
        step_type: str = "general",
        input_data: Dict[str, Any] = None
    ):
        self.step_name = step_name
        self.step_type = step_type
        self.input_data = input_data or {}
        self.ctx = None
        self.step = None
    
    def __enter__(self):
        self.ctx = _trace_context.get()
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


def trace_step(step_name: str, input_data: Dict[str, Any] = None):
    """
    追踪步骤上下文管理器
    
    兼容 rag_trace.py 的 trace_step 函数
    
    Usage:
        with trace_step("query_rewrite", {"query": query}):
            result = await rewriter.rewrite(query)
    """
    return TraceStepContext(step_name, "rag", input_data)


def memory_trace_step(step_name: str, step_type: str = "general", input_data: Dict[str, Any] = None):
    """
    记忆追踪步骤上下文管理器
    
    兼容 memory_trace.py 的 memory_trace_step 函数
    
    Usage:
        with memory_trace_step("finalize_conversation", "general", {...}):
            ...
    """
    return TraceStepContext(step_name, step_type, input_data)


def skill_trace_step(step_name: str, input_data: Dict[str, Any] = None):
    """技能追踪步骤上下文管理器"""
    return TraceStepContext(step_name, "skill", input_data)


def chat_trace_step(step_name: str, input_data: Dict[str, Any] = None):
    """对话追踪步骤上下文管理器"""
    return TraceStepContext(step_name, "chat", input_data)


def traced(step_name: str, step_type: str = "general"):
    """
    追踪装饰器
    
    Usage:
        @traced("my_function", "rag")
        async def my_function():
            ...
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with TraceStepContext(step_name, step_type):
                return await func(*args, **kwargs)
        return async_wrapper
    return decorator


class UnifiedTracer:
    """
    统一追踪器
    
    提供统一的追踪接口，整合所有追踪功能
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def start_rag_trace(self, query: str, metadata: Dict[str, Any] = None) -> UnifiedTraceContext:
        """开始 RAG 追踪"""
        return start_rag_trace(query, metadata)
    
    def start_memory_trace(self, operation: str, metadata: Dict[str, Any] = None) -> UnifiedTraceContext:
        """开始记忆追踪"""
        return start_memory_trace(operation, metadata)
    
    def start_skill_trace(self, skill_name: str, metadata: Dict[str, Any] = None) -> UnifiedTraceContext:
        """开始技能追踪"""
        return start_skill_trace(skill_name, metadata)
    
    def start_chat_trace(self, conversation_id: str, metadata: Dict[str, Any] = None) -> UnifiedTraceContext:
        """开始对话追踪"""
        return start_chat_trace(conversation_id, metadata)
    
    def get_trace(self) -> Optional[UnifiedTraceContext]:
        """获取当前追踪"""
        return get_trace()
    
    def end_trace(self, output: str = None, error: str = None) -> Optional[Dict[str, Any]]:
        """结束当前追踪"""
        return end_trace(output, error)
    
    def trace_step(self, step_name: str, input_data: Dict[str, Any] = None) -> TraceStepContext:
        """创建追踪步骤"""
        return trace_step(step_name, input_data)
    
    def memory_trace_step(self, step_name: str, step_type: str = "general", input_data: Dict[str, Any] = None) -> TraceStepContext:
        """创建记忆追踪步骤"""
        return memory_trace_step(step_name, step_type, input_data)
    
    def skill_trace_step(self, step_name: str, input_data: Dict[str, Any] = None) -> TraceStepContext:
        """创建技能追踪步骤"""
        return skill_trace_step(step_name, input_data)


def get_unified_tracer() -> UnifiedTracer:
    """获取统一追踪器实例"""
    return UnifiedTracer()

"""
图执行追踪模块

追踪 LangGraph 图的执行过程，记录每个节点的执行情况
"""
import time
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
import json

logger = logging.getLogger(__name__)


@dataclass
class NodeExecution:
    """节点执行记录"""
    node_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None
    input_state: Optional[Dict[str, Any]] = None
    output_state: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_name": self.node_name,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class GraphTrace:
    """图执行追踪记录"""
    trace_id: str
    query: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_duration_ms: float = 0.0
    node_executions: List[NodeExecution] = field(default_factory=list)
    final_state: Optional[Dict[str, Any]] = None
    success: bool = True
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "query": self.query,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_duration_ms": self.total_duration_ms,
            "node_executions": [e.to_dict() for e in self.node_executions],
            "success": self.success,
            "error": self.error,
        }
    
    def get_report(self) -> str:
        """生成追踪报告"""
        lines = [
            "=" * 60,
            f"Graph Trace Report: {self.trace_id}",
            "=" * 60,
            f"Query: {self.query}",
            f"Start: {self.start_time.isoformat() if self.start_time else 'N/A'}",
            f"End: {self.end_time.isoformat() if self.end_time else 'N/A'}",
            f"Total Duration: {self.total_duration_ms:.1f}ms",
            f"Success: {self.success}",
            "",
            "Node Executions:",
            "-" * 40,
        ]
        
        for i, execution in enumerate(self.node_executions, 1):
            status = "✅" if execution.success else "❌"
            lines.append(
                f"  {i}. {execution.node_name} [{status}] "
                f"({execution.duration_ms:.1f}ms)"
            )
            if execution.error:
                lines.append(f"     Error: {execution.error}")
        
        if self.error:
            lines.extend([
                "",
                "Error:",
                "-" * 40,
                self.error,
            ])
        
        lines.append("=" * 60)
        return "\n".join(lines)


class GraphTracer:
    """
    图执行追踪器
    
    记录图执行的详细信息，用于调试和分析
    """
    
    def __init__(self):
        self._traces: Dict[str, GraphTrace] = {}
        self._current_trace: Optional[GraphTrace] = None
        self._enabled: bool = True
    
    def enable(self):
        """启用追踪"""
        self._enabled = True
    
    def disable(self):
        """禁用追踪"""
        self._enabled = False
    
    def start_trace(self, trace_id: str, query: str) -> GraphTrace:
        """
        开始追踪
        
        Args:
            trace_id: 追踪 ID
            query: 查询内容
            
        Returns:
            GraphTrace 实例
        """
        if not self._enabled:
            return GraphTrace(
                trace_id=trace_id,
                query=query,
                start_time=datetime.now(),
            )
        
        trace = GraphTrace(
            trace_id=trace_id,
            query=query,
            start_time=datetime.now(),
        )
        
        self._traces[trace_id] = trace
        self._current_trace = trace
        
        logger.info(f"[GraphTracer] Started trace: {trace_id}")
        
        return trace
    
    def record_node_start(
        self,
        node_name: str,
        input_state: Optional[Dict[str, Any]] = None,
    ) -> NodeExecution:
        """
        记录节点开始执行
        
        Args:
            node_name: 节点名称
            input_state: 输入状态
            
        Returns:
            NodeExecution 实例
        """
        execution = NodeExecution(
            node_name=node_name,
            start_time=datetime.now(),
            input_state=input_state,
        )
        
        if self._current_trace:
            self._current_trace.node_executions.append(execution)
        
        logger.debug(f"[GraphTracer] Node started: {node_name}")
        
        return execution
    
    def record_node_end(
        self,
        execution: NodeExecution,
        output_state: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error: Optional[str] = None,
    ):
        """
        记录节点执行结束
        
        Args:
            execution: NodeExecution 实例
            output_state: 输出状态
            success: 是否成功
            error: 错误信息
        """
        execution.end_time = datetime.now()
        execution.duration_ms = (
            (execution.end_time - execution.start_time).total_seconds() * 1000
        )
        execution.output_state = output_state
        execution.success = success
        execution.error = error
        
        status = "success" if success else "failed"
        logger.debug(f"[GraphTracer] Node ended: {execution.node_name} ({status}, {execution.duration_ms:.1f}ms)")
    
    def end_trace(
        self,
        trace_id: str,
        final_state: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error: Optional[str] = None,
    ) -> GraphTrace:
        """
        结束追踪
        
        Args:
            trace_id: 追踪 ID
            final_state: 最终状态
            success: 是否成功
            error: 错误信息
            
        Returns:
            GraphTrace 实例
        """
        trace = self._traces.get(trace_id)
        
        if not trace:
            logger.warning(f"[GraphTracer] Trace not found: {trace_id}")
            return GraphTrace(
                trace_id=trace_id,
                query="",
                start_time=datetime.now(),
            )
        
        trace.end_time = datetime.now()
        trace.total_duration_ms = (
            (trace.end_time - trace.start_time).total_seconds() * 1000
        )
        trace.final_state = final_state
        trace.success = success
        trace.error = error
        
        if self._current_trace and self._current_trace.trace_id == trace_id:
            self._current_trace = None
        
        logger.info(f"[GraphTracer] Ended trace: {trace_id} ({'success' if success else 'failed'}, {trace.total_duration_ms:.1f}ms)")
        
        return trace
    
    def get_trace(self, trace_id: str) -> Optional[GraphTrace]:
        """获取追踪记录"""
        return self._traces.get(trace_id)
    
    def get_all_traces(self) -> List[GraphTrace]:
        """获取所有追踪记录"""
        return list(self._traces.values())
    
    def clear_traces(self):
        """清空追踪记录"""
        self._traces.clear()
        self._current_trace = None
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self._traces:
            return {
                "total_traces": 0,
                "successful_traces": 0,
                "failed_traces": 0,
                "avg_duration_ms": 0,
            }
        
        successful = sum(1 for t in self._traces.values() if t.success)
        failed = len(self._traces) - successful
        avg_duration = sum(t.total_duration_ms for t in self._traces.values()) / len(self._traces)
        
        return {
            "total_traces": len(self._traces),
            "successful_traces": successful,
            "failed_traces": failed,
            "avg_duration_ms": round(avg_duration, 2),
        }


_graph_tracer = GraphTracer()


def get_graph_tracer() -> GraphTracer:
    """获取全局图追踪器"""
    return _graph_tracer


def traced_node(node_name: str):
    """
    节点追踪装饰器
    
    自动记录节点的执行情况
    
    Args:
        node_name: 节点名称
        
    Usage:
        @traced_node("my_node")
        async def my_node_func(state):
            return {"result": "value"}
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(state, *args, **kwargs):
            tracer = get_graph_tracer()
            execution = tracer.record_node_start(node_name, state)
            
            try:
                result = await func(state, *args, **kwargs)
                tracer.record_node_end(execution, result, success=True)
                return result
            except Exception as e:
                tracer.record_node_end(execution, None, success=False, error=str(e))
                raise
        
        @wraps(func)
        def sync_wrapper(state, *args, **kwargs):
            tracer = get_graph_tracer()
            execution = tracer.record_node_start(node_name, state)
            
            try:
                result = func(state, *args, **kwargs)
                tracer.record_node_end(execution, result, success=True)
                return result
            except Exception as e:
                tracer.record_node_end(execution, None, success=False, error=str(e))
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator

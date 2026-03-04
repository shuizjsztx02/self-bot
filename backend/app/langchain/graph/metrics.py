"""
LangGraph 指标收集模块

提供 Prometheus 指标收集和 A/B 测试支持
"""
import time
import logging
from typing import Dict, Any, Optional, Callable
from functools import wraps
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("[Metrics] prometheus_client not installed, metrics collection disabled")


class MetricsCollector:
    """
    指标收集器
    
    收集 LangGraph 执行过程中的各种指标
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._metrics = {
            "requests": {
                "total": 0,
                "success": 0,
                "error": 0,
                "by_architecture": {"new": 0, "old": 0},
                "by_intent": {},
            },
            "durations": {
                "total_ms": 0.0,
                "count": 0,
                "by_node": {},
            },
            "nodes": {
                "executions": 0,
                "success": 0,
                "error": 0,
                "by_name": {},
            },
        }
        
        if PROMETHEUS_AVAILABLE:
            self._init_prometheus_metrics()
    
    def _init_prometheus_metrics(self):
        """初始化 Prometheus 指标"""
        self._counter_requests = Counter(
            'langgraph_requests_total',
            'Total number of LangGraph requests',
            ['architecture', 'intent', 'status']
        )
        
        self._histogram_duration = Histogram(
            'langgraph_request_duration_seconds',
            'Request duration in seconds',
            ['architecture', 'node'],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
        )
        
        self._counter_nodes = Counter(
            'langgraph_node_executions_total',
            'Total number of node executions',
            ['node_name', 'status']
        )
        
        self._histogram_node_duration = Histogram(
            'langgraph_node_duration_seconds',
            'Node execution duration in seconds',
            ['node_name'],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
        )
        
        self._gauge_active = Gauge(
            'langgraph_active_requests',
            'Number of active requests',
            ['architecture']
        )
        
        self._info = Info(
            'langgraph',
            'LangGraph architecture information'
        )
        self._info.info({'version': '1.0.0'})
    
    def record_request(
        self,
        architecture: str,
        intent: str,
        status: str,
        duration_ms: float,
    ):
        """
        记录请求
        
        Args:
            architecture: 架构类型 (new/old)
            intent: 意图类型
            status: 状态 (success/error)
            duration_ms: 持续时间（毫秒）
        """
        self._metrics["requests"]["total"] += 1
        self._metrics["requests"]["by_architecture"][architecture] = \
            self._metrics["requests"]["by_architecture"].get(architecture, 0) + 1
        
        if status == "success":
            self._metrics["requests"]["success"] += 1
        else:
            self._metrics["requests"]["error"] += 1
        
        if intent not in self._metrics["requests"]["by_intent"]:
            self._metrics["requests"]["by_intent"][intent] = 0
        self._metrics["requests"]["by_intent"][intent] += 1
        
        self._metrics["durations"]["total_ms"] += duration_ms
        self._metrics["durations"]["count"] += 1
        
        if PROMETHEUS_AVAILABLE:
            self._counter_requests.labels(
                architecture=architecture,
                intent=intent or "unknown",
                status=status,
            ).inc()
            
            self._histogram_duration.labels(
                architecture=architecture,
                node="total",
            ).observe(duration_ms / 1000)
    
    def record_node(
        self,
        node_name: str,
        success: bool,
        duration_ms: float,
    ):
        """
        记录节点执行
        
        Args:
            node_name: 节点名称
            success: 是否成功
            duration_ms: 持续时间（毫秒）
        """
        self._metrics["nodes"]["executions"] += 1
        
        if success:
            self._metrics["nodes"]["success"] += 1
        else:
            self._metrics["nodes"]["error"] += 1
        
        if node_name not in self._metrics["nodes"]["by_name"]:
            self._metrics["nodes"]["by_name"][node_name] = {
                "count": 0,
                "success": 0,
                "error": 0,
                "total_ms": 0.0,
            }
        
        self._metrics["nodes"]["by_name"][node_name]["count"] += 1
        self._metrics["nodes"]["by_name"][node_name]["total_ms"] += duration_ms
        
        if success:
            self._metrics["nodes"]["by_name"][node_name]["success"] += 1
        else:
            self._metrics["nodes"]["by_name"][node_name]["error"] += 1
        
        if PROMETHEUS_AVAILABLE:
            self._counter_nodes.labels(
                node_name=node_name,
                status="success" if success else "error",
            ).inc()
            
            self._histogram_node_duration.labels(
                node_name=node_name,
            ).observe(duration_ms / 1000)
    
    def start_request(self, architecture: str):
        """开始请求"""
        if PROMETHEUS_AVAILABLE:
            self._gauge_active.labels(architecture=architecture).inc()
    
    def end_request(self, architecture: str):
        """结束请求"""
        if PROMETHEUS_AVAILABLE:
            self._gauge_active.labels(architecture=architecture).dec()
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取指标摘要"""
        result = {
            "requests": dict(self._metrics["requests"]),
            "durations": dict(self._metrics["durations"]),
            "nodes": dict(self._metrics["nodes"]),
        }
        
        if result["durations"]["count"] > 0:
            result["durations"]["avg_ms"] = (
                result["durations"]["total_ms"] / result["durations"]["count"]
            )
        else:
            result["durations"]["avg_ms"] = 0.0
        
        if result["requests"]["total"] > 0:
            result["requests"]["error_rate"] = (
                result["requests"]["error"] / result["requests"]["total"]
            )
            result["requests"]["success_rate"] = (
                result["requests"]["success"] / result["requests"]["total"]
            )
        else:
            result["requests"]["error_rate"] = 0.0
            result["requests"]["success_rate"] = 1.0
        
        return result
    
    def get_prometheus_metrics(self) -> Optional[bytes]:
        """获取 Prometheus 格式的指标"""
        if PROMETHEUS_AVAILABLE:
            return generate_latest()
        return None
    
    def reset(self):
        """重置指标"""
        self._metrics = {
            "requests": {
                "total": 0,
                "success": 0,
                "error": 0,
                "by_architecture": {"new": 0, "old": 0},
                "by_intent": {},
            },
            "durations": {
                "total_ms": 0.0,
                "count": 0,
                "by_node": {},
            },
            "nodes": {
                "executions": 0,
                "success": 0,
                "error": 0,
                "by_name": {},
            },
        }


_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """获取全局指标收集器"""
    return _metrics_collector


def with_metrics(node_name: str):
    """
    节点指标装饰器
    
    自动收集节点执行指标
    
    Usage:
        @with_metrics("my_node")
        async def my_node_func(state):
            return {"result": "value"}
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(state, *args, **kwargs):
            collector = get_metrics_collector()
            start_time = time.time()
            
            try:
                result = await func(state, *args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                collector.record_node(node_name, True, duration_ms)
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                collector.record_node(node_name, False, duration_ms)
                raise
        
        @wraps(func)
        def sync_wrapper(state, *args, **kwargs):
            collector = get_metrics_collector()
            start_time = time.time()
            
            try:
                result = func(state, *args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                collector.record_node(node_name, True, duration_ms)
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                collector.record_node(node_name, False, duration_ms)
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


class ABTestAnalyzer:
    """
    A/B 测试分析器
    
    分析新旧架构的性能差异
    """
    
    def __init__(self):
        self.collector = get_metrics_collector()
    
    def analyze(self) -> Dict[str, Any]:
        """
        分析 A/B 测试结果
        
        Returns:
            分析报告
        """
        metrics = self.collector.get_metrics()
        
        new_requests = metrics["requests"]["by_architecture"].get("new", 0)
        old_requests = metrics["requests"]["by_architecture"].get("old", 0)
        total = new_requests + old_requests
        
        if total == 0:
            return {
                "status": "no_data",
                "message": "暂无数据",
                "total_requests": 0,
            }
        
        new_ratio = new_requests / total
        old_ratio = old_requests / total
        
        report = {
            "status": "ok",
            "total_requests": total,
            "traffic_distribution": {
                "new_architecture": {
                    "requests": new_requests,
                    "ratio": f"{new_ratio:.1%}",
                },
                "old_architecture": {
                    "requests": old_requests,
                    "ratio": f"{old_ratio:.1%}",
                },
            },
            "overall": {
                "success_rate": f"{metrics['requests']['success_rate']:.1%}",
                "error_rate": f"{metrics['requests']['error_rate']:.1%}",
                "avg_duration_ms": f"{metrics['durations']['avg_ms']:.1f}",
            },
            "nodes": {},
        }
        
        for node_name, node_metrics in metrics["nodes"]["by_name"].items():
            if node_metrics["count"] > 0:
                avg_ms = node_metrics["total_ms"] / node_metrics["count"]
                error_rate = node_metrics["error"] / node_metrics["count"]
                
                report["nodes"][node_name] = {
                    "executions": node_metrics["count"],
                    "avg_duration_ms": f"{avg_ms:.1f}",
                    "error_rate": f"{error_rate:.1%}",
                }
        
        if new_requests > 0 and old_requests > 0:
            report["recommendation"] = self._generate_recommendation(metrics)
        
        return report
    
    def _generate_recommendation(self, metrics: Dict) -> str:
        """生成推荐建议"""
        error_rate = metrics["requests"]["error_rate"]
        
        if error_rate > 0.05:
            return "⚠️ 错误率较高，建议检查系统稳定性"
        elif error_rate > 0.01:
            return "⚡ 错误率略高，建议关注异常情况"
        else:
            return "✅ 系统运行正常，可以考虑扩大新架构流量"


_ab_test_analyzer = ABTestAnalyzer()


def get_ab_test_analyzer() -> ABTestAnalyzer:
    """获取 A/B 测试分析器"""
    return _ab_test_analyzer

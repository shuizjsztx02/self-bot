# Self-Bot 熔断降级设计方案

## 一、设计目标

1. **服务可用性**: 单点故障不影响整体服务
2. **快速失败**: 避免级联故障和资源耗尽
3. **优雅降级**: 保证核心功能可用
4. **自动恢复**: 服务恢复后自动切换回正常模式

## 二、架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           请求入口层                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      API Gateway / Router                        │   │
│  └──────────────────────────────┬──────────────────────────────────┘   │
└─────────────────────────────────┼──────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           熔断降级层                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │CircuitBreaker│  │RetryStrategy │  │DegradationMgr│                  │
│  │  (熔断器)    │  │  (重试策略)  │  │  (降级管理)  │                  │
│  └──────────────┘  └──────────────┘  └──────────────┘                  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                     HealthChecker (健康检查)                      │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           服务调用层                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │  LLM Service │  │Embedding Svc │  │ Vector Store │                  │
│  │  (多Provider)│  │  (本地模型)  │  │  (ChromaDB)  │                  │
│  └──────────────┘  └──────────────┘  └──────────────┘                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │  MCP Client  │  │ Search Tools │  │ Memory Store │                  │
│  │  (工具调用)  │  │  (网络搜索)  │  │  (记忆存储)  │                  │
│  └──────────────┘  └──────────────┘  └──────────────┘                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

| 组件 | 职责 | 配置项 |
|------|------|--------|
| CircuitBreaker | 熔断器状态管理 | 失败阈值、恢复超时、半开请求数 |
| RetryStrategy | 重试策略执行 | 重试次数、退避策略、抖动 |
| DegradationManager | 降级决策与执行 | 降级规则、降级顺序、恢复策略 |
| HealthChecker | 服务健康检查 | 检查间隔、超时时间、检查端点 |
| MetricsCollector | 指标收集与监控 | 成功率、延迟、错误类型 |

## 三、熔断器设计

### 3.1 熔断器配置

```python
# backend/app/core/resilience/config.py

from dataclasses import dataclass, field
from typing import Tuple, Type
from enum import Enum


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    
    failure_threshold: int = 5
    success_threshold: int = 3
    recovery_timeout: float = 60.0
    half_open_max_calls: int = 3
    
    expected_exceptions: Tuple[Type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        OSError,
    )
    
    excluded_exceptions: Tuple[Type[Exception], ...] = (
        ValueError,
        TypeError,
        KeyError,
    )


@dataclass
class RetryConfig:
    """重试配置"""
    
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.5
    
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
    )


@dataclass
class ServiceConfig:
    """服务级别配置"""
    
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    timeout: float = 30.0
    
    enable_circuit_breaker: bool = True
    enable_retry: bool = True


SERVICE_CONFIGS = {
    "llm_openai": ServiceConfig(
        circuit_breaker=CircuitBreakerConfig(failure_threshold=3, recovery_timeout=120),
        retry=RetryConfig(max_retries=3, base_delay=2.0),
        timeout=60.0,
    ),
    "llm_deepseek": ServiceConfig(
        circuit_breaker=CircuitBreakerConfig(failure_threshold=5, recovery_timeout=60),
        retry=RetryConfig(max_retries=2, base_delay=1.0),
        timeout=30.0,
    ),
    "embedding": ServiceConfig(
        circuit_breaker=CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30),
        retry=RetryConfig(max_retries=2, base_delay=0.5),
        timeout=10.0,
    ),
    "vector_store": ServiceConfig(
        circuit_breaker=CircuitBreakerConfig(failure_threshold=5, recovery_timeout=30),
        retry=RetryConfig(max_retries=3, base_delay=0.5),
        timeout=5.0,
    ),
    "mcp_client": ServiceConfig(
        circuit_breaker=CircuitBreakerConfig(failure_threshold=3, recovery_timeout=60),
        retry=RetryConfig(max_retries=2, base_delay=1.0),
        timeout=30.0,
    ),
    "search_tavily": ServiceConfig(
        circuit_breaker=CircuitBreakerConfig(failure_threshold=3, recovery_timeout=60),
        retry=RetryConfig(max_retries=2, base_delay=1.0),
        timeout=15.0,
    ),
}
```

### 3.2 熔断器实现

```python
# backend/app/core/resilience/circuit_breaker.py

import asyncio
import time
import logging
from typing import Callable, Any, Optional, Dict
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager

from .config import CircuitBreakerConfig, CircuitState

logger = logging.getLogger(__name__)


@dataclass
class CircuitStats:
    """熔断器统计信息"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_error: Optional[Exception] = None


class CircuitBreakerOpen(Exception):
    """熔断器打开异常"""
    def __init__(self, service_name: str, recovery_timeout: float, stats: CircuitStats):
        self.service_name = service_name
        self.recovery_timeout = recovery_timeout
        self.stats = stats
        super().__init__(
            f"Circuit breaker is OPEN for service '{service_name}'. "
            f"Will retry after {recovery_timeout}s. "
            f"Consecutive failures: {stats.consecutive_failures}"
        )


class CircuitBreaker:
    """
    熔断器实现
    
    状态转换：
    CLOSED -> OPEN: 连续失败次数达到阈值
    OPEN -> HALF_OPEN: 恢复超时后
    HALF_OPEN -> CLOSED: 连续成功次数达到阈值
    HALF_OPEN -> OPEN: 任意失败
    """
    
    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig = None,
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._lock = asyncio.Lock()
        self._half_open_calls = 0
    
    @property
    def state(self) -> CircuitState:
        return self._state
    
    @property
    def stats(self) -> CircuitStats:
        return self._stats
    
    @property
    def is_closed(self) -> bool:
        return self._state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                return False
            return True
        return False
    
    @property
    def is_half_open(self) -> bool:
        return self._state == CircuitState.HALF_OPEN
    
    def _should_attempt_reset(self) -> bool:
        if self._stats.last_failure_time is None:
            return True
        elapsed = time.time() - self._stats.last_failure_time
        return elapsed >= self.config.recovery_timeout
    
    async def _transition_to_open(self):
        if self._state != CircuitState.OPEN:
            logger.warning(
                f"Circuit breaker '{self.name}' transitioning to OPEN. "
                f"Consecutive failures: {self._stats.consecutive_failures}"
            )
        self._state = CircuitState.OPEN
        self._half_open_calls = 0
    
    async def _transition_to_closed(self):
        if self._state != CircuitState.CLOSED:
            logger.info(
                f"Circuit breaker '{self.name}' transitioning to CLOSED. "
                f"Service recovered after {self._stats.consecutive_failures} failures."
            )
        self._state = CircuitState.CLOSED
        self._stats.consecutive_failures = 0
        self._stats.consecutive_successes = 0
        self._half_open_calls = 0
    
    async def _transition_to_half_open(self):
        if self._state != CircuitState.HALF_OPEN:
            logger.info(
                f"Circuit breaker '{self.name}' transitioning to HALF_OPEN. "
                f"Attempting recovery..."
            )
        self._state = CircuitState.HALF_OPEN
        self._half_open_calls = 0
    
    async def _record_success(self):
        async with self._lock:
            self._stats.total_calls += 1
            self._stats.successful_calls += 1
            self._stats.last_success_time = time.time()
            self._stats.consecutive_successes += 1
            self._stats.consecutive_failures = 0
            
            if self._state == CircuitState.HALF_OPEN:
                if self._stats.consecutive_successes >= self.config.success_threshold:
                    await self._transition_to_closed()
    
    async def _record_failure(self, error: Exception):
        async with self._lock:
            self._stats.total_calls += 1
            self._stats.failed_calls += 1
            self._stats.last_failure_time = time.time()
            self._stats.consecutive_failures += 1
            self._stats.consecutive_successes = 0
            self._stats.last_error = error
            
            if self._state == CircuitState.HALF_OPEN:
                await self._transition_to_open()
            elif self._stats.consecutive_failures >= self.config.failure_threshold:
                await self._transition_to_open()
    
    async def _record_rejection(self):
        async with self._lock:
            self._stats.rejected_calls += 1
    
    def _is_expected_exception(self, error: Exception) -> bool:
        for exc_type in self.config.excluded_exceptions:
            if isinstance(error, exc_type):
                return False
        for exc_type in self.config.expected_exceptions:
            if isinstance(error, exc_type):
                return True
        return False
    
    @asynccontextmanager
    async def _check_state(self):
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                await self._transition_to_half_open()
            else:
                await self._record_rejection()
                raise CircuitBreakerOpen(
                    self.name, 
                    self.config.recovery_timeout - (time.time() - self._stats.last_failure_time),
                    self._stats
                )
        
        if self._state == CircuitState.HALF_OPEN:
            if self._half_open_calls >= self.config.half_open_max_calls:
                await self._record_rejection()
                raise CircuitBreakerOpen(
                    self.name,
                    0,
                    self._stats
                )
            self._half_open_calls += 1
        
        try:
            yield
        except Exception as e:
            if self._is_expected_exception(e):
                await self._record_failure(e)
            raise
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        通过熔断器执行异步函数
        """
        async with self._check_state():
            result = await func(*args, **kwargs)
            await self._record_success()
            return result
    
    def call_sync(self, func: Callable, *args, **kwargs) -> Any:
        """
        通过熔断器执行同步函数
        """
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
            else:
                self._stats.rejected_calls += 1
                raise CircuitBreakerOpen(
                    self.name,
                    self.config.recovery_timeout,
                    self._stats
                )
        
        try:
            result = func(*args, **kwargs)
            self._stats.total_calls += 1
            self._stats.successful_calls += 1
            self._stats.last_success_time = time.time()
            self._stats.consecutive_successes += 1
            self._stats.consecutive_failures = 0
            
            if self._state == CircuitState.HALF_OPEN:
                if self._stats.consecutive_successes >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
            
            return result
        except Exception as e:
            if self._is_expected_exception(e):
                self._stats.total_calls += 1
                self._stats.failed_calls += 1
                self._stats.last_failure_time = time.time()
                self._stats.consecutive_failures += 1
                self._stats.consecutive_successes = 0
                self._stats.last_error = e
                
                if self._state == CircuitState.HALF_OPEN:
                    self._state = CircuitState.OPEN
                elif self._stats.consecutive_failures >= self.config.failure_threshold:
                    self._state = CircuitState.OPEN
            raise
    
    def reset(self):
        """手动重置熔断器"""
        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._half_open_calls = 0
        logger.info(f"Circuit breaker '{self.name}' has been reset")
    
    def force_open(self):
        """强制打开熔断器"""
        self._state = CircuitState.OPEN
        self._stats.last_failure_time = time.time()
        logger.warning(f"Circuit breaker '{self.name}' has been forced OPEN")
    
    def get_status(self) -> Dict[str, Any]:
        """获取熔断器状态"""
        return {
            "name": self.name,
            "state": self._state.value,
            "stats": {
                "total_calls": self._stats.total_calls,
                "successful_calls": self._stats.successful_calls,
                "failed_calls": self._stats.failed_calls,
                "rejected_calls": self._stats.rejected_calls,
                "consecutive_failures": self._stats.consecutive_failures,
                "consecutive_successes": self._stats.consecutive_successes,
                "last_failure_time": self._stats.last_failure_time,
                "last_success_time": self._stats.last_success_time,
                "last_error": str(self._stats.last_error) if self._stats.last_error else None,
            },
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "recovery_timeout": self.config.recovery_timeout,
            }
        }
```

### 3.3 重试策略实现

```python
# backend/app/core/resilience/retry.py

import asyncio
import random
import logging
from typing import Callable, Any, Tuple, Type, Optional
from functools import wraps

from .config import RetryConfig

logger = logging.getLogger(__name__)


class RetryExhausted(Exception):
    """重试耗尽异常"""
    def __init__(self, attempts: int, last_error: Exception):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"All {attempts} retry attempts exhausted. Last error: {last_error}"
        )


def calculate_delay(
    attempt: int,
    config: RetryConfig,
) -> float:
    """计算重试延迟（指数退避 + 抖动）"""
    delay = min(
        config.base_delay * (config.exponential_base ** attempt),
        config.max_delay
    )
    
    if config.jitter:
        jitter_range = delay * config.jitter_factor
        delay = delay + random.uniform(-jitter_range, jitter_range)
    
    return max(0, delay)


async def retry_async(
    func: Callable,
    config: RetryConfig = None,
    *args,
    **kwargs,
) -> Any:
    """
    异步重试执行
    """
    config = config or RetryConfig()
    last_error: Optional[Exception] = None
    
    for attempt in range(config.max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except config.retryable_exceptions as e:
            last_error = e
            
            if attempt == config.max_retries:
                logger.error(
                    f"Retry exhausted for {func.__name__} after {attempt + 1} attempts. "
                    f"Last error: {e}"
                )
                raise RetryExhausted(attempt + 1, e)
            
            delay = calculate_delay(attempt, config)
            logger.warning(
                f"Retry attempt {attempt + 1}/{config.max_retries} for {func.__name__}. "
                f"Error: {e}. Retrying in {delay:.2f}s..."
            )
            await asyncio.sleep(delay)
        except Exception as e:
            raise
    
    raise last_error


def retry_sync(
    func: Callable,
    config: RetryConfig = None,
    *args,
    **kwargs,
) -> Any:
    """
    同步重试执行
    """
    import time
    config = config or RetryConfig()
    last_error: Optional[Exception] = None
    
    for attempt in range(config.max_retries + 1):
        try:
            return func(*args, **kwargs)
        except config.retryable_exceptions as e:
            last_error = e
            
            if attempt == config.max_retries:
                logger.error(
                    f"Retry exhausted for {func.__name__} after {attempt + 1} attempts"
                )
                raise RetryExhausted(attempt + 1, e)
            
            delay = calculate_delay(attempt, config)
            logger.warning(
                f"Retry attempt {attempt + 1}/{config.max_retries} for {func.__name__}. "
                f"Retrying in {delay:.2f}s..."
            )
            time.sleep(delay)
        except Exception as e:
            raise
    
    raise last_error


def with_retry(config: RetryConfig = None):
    """
    重试装饰器
    """
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await retry_async(func, config, *args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return retry_sync(func, config, *args, **kwargs)
            return sync_wrapper
    return decorator
```

## 四、降级策略设计

### 4.1 降级管理器

```python
# backend/app/core/resilience/degradation.py

import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DegradationLevel(str, Enum):
    """降级级别"""
    NORMAL = "normal"           # 正常服务
    DEGRADED = "degraded"       # 部分降级
    MINIMAL = "minimal"         # 最小服务
    EMERGENCY = "emergency"     # 紧急模式


@dataclass
class DegradationRule:
    """降级规则"""
    name: str
    trigger_condition: Callable[[Dict], bool]
    action: Callable
    recovery_condition: Callable[[Dict], bool]
    recovery_action: Optional[Callable] = None
    priority: int = 0
    enabled: bool = True


@dataclass
class ServiceStatus:
    """服务状态"""
    name: str
    healthy: bool = True
    last_check: Optional[datetime] = None
    error_count: int = 0
    last_error: Optional[str] = None
    degradation_level: DegradationLevel = DegradationLevel.NORMAL


class DegradationManager:
    """
    降级管理器
    
    管理服务的降级策略和恢复机制
    """
    
    def __init__(self):
        self._services: Dict[str, ServiceStatus] = {}
        self._rules: List[DegradationRule] = []
        self._fallback_handlers: Dict[str, Callable] = {}
        self._current_level: DegradationLevel = DegradationLevel.NORMAL
        self._degraded_features: set = set()
    
    def register_service(
        self,
        name: str,
        fallback_handler: Callable = None,
    ):
        """注册服务"""
        self._services[name] = ServiceStatus(name=name)
        if fallback_handler:
            self._fallback_handlers[name] = fallback_handler
        logger.info(f"Registered service: {name}")
    
    def register_rule(self, rule: DegradationRule):
        """注册降级规则"""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)
        logger.info(f"Registered degradation rule: {rule.name}")
    
    def update_service_status(
        self,
        name: str,
        healthy: bool,
        error: Optional[str] = None,
    ):
        """更新服务状态"""
        if name not in self._services:
            logger.warning(f"Unknown service: {name}")
            return
        
        status = self._services[name]
        status.healthy = healthy
        status.last_check = datetime.now()
        
        if not healthy:
            status.error_count += 1
            status.last_error = error
        else:
            status.error_count = 0
        
        self._evaluate_degradation()
    
    def _evaluate_degradation(self):
        """评估降级状态"""
        context = {
            "services": self._services,
            "current_level": self._current_level,
            "degraded_features": self._degraded_features,
        }
        
        for rule in self._rules:
            if not rule.enabled:
                continue
            
            try:
                if rule.trigger_condition(context):
                    logger.warning(f"Degradation rule triggered: {rule.name}")
                    asyncio.create_task(self._execute_action(rule.action, context))
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.name}: {e}")
    
    async def _execute_action(self, action: Callable, context: Dict):
        """执行降级动作"""
        try:
            if asyncio.iscoroutinefunction(action):
                await action(context)
            else:
                action(context)
        except Exception as e:
            logger.error(f"Error executing degradation action: {e}")
    
    async def execute_with_fallback(
        self,
        service_name: str,
        primary_func: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """带降级执行"""
        status = self._services.get(service_name)
        
        if status and not status.healthy:
            if service_name in self._fallback_handlers:
                logger.info(f"Using fallback for service: {service_name}")
                return await self._fallback_handlers[service_name](*args, **kwargs)
            else:
                raise ServiceDegradedError(
                    f"Service {service_name} is degraded and no fallback available"
                )
        
        try:
            if asyncio.iscoroutinefunction(primary_func):
                result = await primary_func(*args, **kwargs)
            else:
                result = primary_func(*args, **kwargs)
            
            self.update_service_status(service_name, healthy=True)
            return result
        except Exception as e:
            self.update_service_status(service_name, healthy=False, error=str(e))
            
            if service_name in self._fallback_handlers:
                logger.info(f"Primary failed, using fallback for: {service_name}")
                return await self._fallback_handlers[service_name](*args, **kwargs)
            
            raise
    
    def get_degraded_features(self) -> set:
        """获取已降级的功能"""
        return self._degraded_features.copy()
    
    def is_feature_available(self, feature: str) -> bool:
        """检查功能是否可用"""
        return feature not in self._degraded_features
    
    def get_status_report(self) -> Dict[str, Any]:
        """获取状态报告"""
        return {
            "current_level": self._current_level.value,
            "services": {
                name: {
                    "healthy": status.healthy,
                    "error_count": status.error_count,
                    "last_error": status.last_error,
                    "degradation_level": status.degradation_level.value,
                }
                for name, status in self._services.items()
            },
            "degraded_features": list(self._degraded_features),
        }


class ServiceDegradedError(Exception):
    """服务降级异常"""
    pass
```

### 4.2 LLM 服务降级配置

```python
# backend/app/core/resilience/llm_resilience.py

import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from .circuit_breaker import CircuitBreaker, CircuitBreakerOpen
from .retry import retry_async, RetryConfig
from .degradation import DegradationManager, DegradationLevel
from .config import SERVICE_CONFIGS, ServiceConfig

logger = logging.getLogger(__name__)


@dataclass
class ProviderStatus:
    """Provider状态"""
    name: str
    circuit_breaker: CircuitBreaker
    priority: int
    available: bool = True


class LLMResilienceManager:
    """
    LLM服务韧性管理器
    
    功能：
    1. 多Provider熔断
    2. 自动故障转移
    3. 降级响应
    """
    
    PROVIDER_PRIORITY = {
        "openai": 1,
        "deepseek": 2,
        "qwen": 3,
        "glm": 4,
        "ollama": 5,
    }
    
    def __init__(self):
        self._providers: Dict[str, ProviderStatus] = {}
        self._fallback_order: List[str] = []
        self._degradation_manager = DegradationManager()
        
        self._initialize_providers()
    
    def _initialize_providers(self):
        """初始化所有Provider的熔断器"""
        for provider, priority in self.PROVIDER_PRIORITY.items():
            config_key = f"llm_{provider}"
            service_config = SERVICE_CONFIGS.get(config_key)
            
            if service_config:
                cb = CircuitBreaker(
                    name=f"llm_{provider}",
                    config=service_config.circuit_breaker,
                )
                self._providers[provider] = ProviderStatus(
                    name=provider,
                    circuit_breaker=cb,
                    priority=priority,
                )
        
        self._fallback_order = sorted(
            self._providers.keys(),
            key=lambda p: self._providers[p].priority
        )
    
    async def execute_with_resilience(
        self,
        provider: str,
        func: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """
        带韧性的执行LLM调用
        
        流程：
        1. 尝试指定Provider
        2. 失败则按优先级尝试备选Provider
        3. 全部失败则返回降级响应
        """
        providers_to_try = [provider] + [
            p for p in self._fallback_order if p != provider
        ]
        
        last_error = None
        
        for current_provider in providers_to_try:
            provider_status = self._providers.get(current_provider)
            if not provider_status:
                continue
            
            if provider_status.circuit_breaker.is_open:
                logger.debug(f"Skipping {current_provider}: circuit breaker open")
                continue
            
            try:
                config = SERVICE_CONFIGS.get(f"llm_{current_provider}")
                
                async def _call():
                    return await provider_status.circuit_breaker.call(
                        func, *args, **kwargs
                    )
                
                if config and config.enable_retry:
                    result = await retry_async(
                        _call,
                        config.retry,
                    )
                else:
                    result = await _call()
                
                return result
                
            except CircuitBreakerOpen:
                logger.warning(f"Circuit breaker open for {current_provider}")
                continue
            except Exception as e:
                logger.error(f"Error calling {current_provider}: {e}")
                last_error = e
                continue
        
        return await self._degraded_response(last_error)
    
    async def _degraded_response(self, error: Optional[Exception]) -> str:
        """生成降级响应"""
        if error:
            logger.error(f"All LLM providers failed. Last error: {error}")
        
        return (
            "抱歉，AI服务当前不可用。请稍后重试，或尝试简化您的问题。\n\n"
            "您可以：\n"
            "1. 稍后重试\n"
            "2. 使用知识库搜索功能\n"
            "3. 联系管理员检查服务状态"
        )
    
    def get_provider_status(self) -> Dict[str, Any]:
        """获取所有Provider状态"""
        return {
            provider: {
                "available": not ps.circuit_breaker.is_open,
                "state": ps.circuit_breaker.state.value,
                "stats": ps.circuit_breaker.stats,
            }
            for provider, ps in self._providers.items()
        }
    
    def reset_provider(self, provider: str):
        """重置指定Provider"""
        if provider in self._providers:
            self._providers[provider].circuit_breaker.reset()
            logger.info(f"Reset circuit breaker for {provider}")
```

## 五、集成应用

### 5.1 LLM服务集成

```python
# backend/app/langchain/llm_resilient.py

from typing import Optional, Dict, Any
import logging

from langchain_core.language_models import BaseChatModel

from app.core.resilience.llm_resilience import LLMResilienceManager
from app.core.resilience.config import SERVICE_CONFIGS

logger = logging.getLogger(__name__)

_resilience_manager: Optional[LLMResilienceManager] = None


def get_resilience_manager() -> LLMResilienceManager:
    """获取全局韧性管理器"""
    global _resilience_manager
    if _resilience_manager is None:
        _resilience_manager = LLMResilienceManager()
    return _resilience_manager


async def get_llm_with_resilience(
    provider: str = None,
    **kwargs,
) -> BaseChatModel:
    """
    获取带韧性保护的LLM实例
    
    使用方式：
    ```python
    llm = await get_llm_with_resilience("openai")
    response = await llm.ainvoke("Hello")
    ```
    """
    from app.langchain.llm import get_llm
    
    provider = provider or settings.DEFAULT_LLM_PROVIDER
    manager = get_resilience_manager()
    
    llm = get_llm(provider, **kwargs)
    
    original_ainvoke = llm.ainvoke
    
    async def resilient_ainvoke(*args, **invoke_kwargs):
        return await manager.execute_with_resilience(
            provider,
            original_ainvoke,
            *args,
            **invoke_kwargs,
        )
    
    llm.ainvoke = resilient_ainvoke
    
    return llm
```

### 5.2 向量存储集成

```python
# backend/app/knowledge_base/vector_store/resilient_store.py

from typing import List, Dict, Any, Optional
import logging
import asyncio

from app.core.resilience.circuit_breaker import CircuitBreaker
from app.core.resilience.retry import retry_async
from app.core.resilience.config import SERVICE_CONFIGS

logger = logging.getLogger(__name__)


class ResilientVectorStore:
    """
    带韧性保护的向量存储
    
    降级策略：
    1. 搜索失败 -> 返回空结果
    2. 写入失败 -> 重试后降级到内存缓存
    3. 连接失败 -> 熔断保护
    """
    
    def __init__(self, backend):
        self._backend = backend
        config = SERVICE_CONFIGS.get("vector_store")
        
        self._circuit_breaker = CircuitBreaker(
            name="vector_store",
            config=config.circuit_breaker if config else None,
        )
        self._retry_config = config.retry if config else None
        
        self._memory_cache: Dict[str, List[Dict]] = {}
    
    async def search(
        self,
        collection_name: str,
        query_embedding: List[float],
        top_k: int = 10,
        **kwargs,
    ) -> List[Dict]:
        """带保护的搜索"""
        try:
            async def _search():
                return await self._backend.search(
                    collection_name, query_embedding, top_k, **kwargs
                )
            
            if self._retry_config:
                return await retry_async(_search, self._retry_config)
            return await _search()
            
        except Exception as e:
            logger.error(f"Vector store search failed: {e}")
            
            if collection_name in self._memory_cache:
                logger.info(f"Using memory cache for {collection_name}")
                return self._memory_cache[collection_name][:top_k]
            
            return []
    
    async def add_vectors(
        self,
        collection_name: str,
        embeddings: List[List[float]],
        metadatas: List[Dict],
        ids: List[str],
    ) -> bool:
        """带保护的向量添加"""
        try:
            async def _add():
                return await self._backend.add_vectors(
                    collection_name, embeddings, metadatas, ids
                )
            
            if self._retry_config:
                return await retry_async(_add, self._retry_config)
            return await _add()
            
        except Exception as e:
            logger.error(f"Vector store add failed: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "circuit_breaker": self._circuit_breaker.get_status(),
            "memory_cache_size": len(self._memory_cache),
        }
```

## 六、监控与告警

### 6.1 健康检查端点

```python
# backend/app/api/health.py

from fastapi import APIRouter, Response
from typing import Dict, Any

from app.core.resilience.llm_resilience import get_resilience_manager

router = APIRouter()


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """健康检查"""
    manager = get_resilience_manager()
    
    return {
        "status": "healthy",
        "providers": manager.get_provider_status(),
    }


@router.get("/health/resilience")
async def resilience_status() -> Dict[str, Any]:
    """韧性系统状态"""
    manager = get_resilience_manager()
    
    return {
        "providers": manager.get_provider_status(),
        "degradation": manager._degradation_manager.get_status_report(),
    }


@router.post("/health/reset/{provider}")
async def reset_provider(provider: str) -> Dict[str, str]:
    """重置Provider熔断器"""
    manager = get_resilience_manager()
    manager.reset_provider(provider)
    
    return {"status": "reset", "provider": provider}
```

### 6.2 Prometheus指标

```python
# backend/app/core/resilience/metrics.py

from prometheus_client import Counter, Histogram, Gauge

CIRCUIT_BREAKER_STATE = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half_open)',
    ['service']
)

CIRCUIT_BREAKER_FAILURES = Counter(
    'circuit_breaker_failures_total',
    'Total circuit breaker failures',
    ['service']
)

RETRY_ATTEMPTS = Counter(
    'retry_attempts_total',
    'Total retry attempts',
    ['service', 'success']
)

SERVICE_LATENCY = Histogram(
    'service_latency_seconds',
    'Service call latency',
    ['service'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

DEGRADATION_EVENTS = Counter(
    'degradation_events_total',
    'Total degradation events',
    ['service', 'level']
)
```

## 七、配置示例

```yaml
# config/resilience.yaml

circuit_breaker:
  default:
    failure_threshold: 5
    success_threshold: 3
    recovery_timeout: 60
  
  llm:
    failure_threshold: 3
    recovery_timeout: 120
  
  vector_store:
    failure_threshold: 5
    recovery_timeout: 30

retry:
  default:
    max_retries: 3
    base_delay: 1.0
    max_delay: 30.0
  
  llm:
    max_retries: 3
    base_delay: 2.0
  
  vector_store:
    max_retries: 3
    base_delay: 0.5

degradation:
  llm_fallback_order:
    - openai
    - deepseek
    - qwen
    - glm
    - ollama
  
  features:
    reranking:
      degrade_on: ["embedding_failure"]
    long_term_memory:
      degrade_on: ["vector_store_failure"]
```

## 八、实施计划

| 阶段 | 任务 | 优先级 | 预估工时 |
|------|------|--------|----------|
| P0 | 实现熔断器核心 | 高 | 2天 |
| P0 | 实现重试策略 | 高 | 1天 |
| P0 | LLM服务集成 | 高 | 2天 |
| P1 | 降级管理器 | 中 | 2天 |
| P1 | 向量存储集成 | 中 | 1天 |
| P1 | 健康检查端点 | 中 | 0.5天 |
| P2 | Prometheus指标 | 低 | 1天 |
| P2 | 监控告警 | 低 | 1天 |

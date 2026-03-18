"""
限流器模块

提供多种限流策略，防止 LLM API 限流错误：
1. TokenBucketLimiter - 令牌桶算法，平滑限流
2. SlidingWindowLimiter - 滑动窗口，精确控制
3. AdaptiveRateLimiter - 自适应限流，根据 429 响应自动调整
4. ConcurrentLimiter - 并发控制，限制同时请求数
"""

import asyncio
import time
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import math

logger = logging.getLogger(__name__)


class RateLimitStrategy(Enum):
    """限流策略"""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    ADAPTIVE = "adaptive"


@dataclass
class RateLimitConfig:
    """限流配置"""
    requests_per_second: float = 10.0
    burst_size: int = 20
    max_concurrent: int = 10
    enable_adaptive: bool = True
    backoff_factor: float = 2.0
    min_delay_ms: float = 100.0
    max_delay_ms: float = 60000.0
    

class TokenBucketLimiter:
    """
    令牌桶限流器
    
    特点：
    - 平滑限流，允许突发流量
    - 适合 API 调用场景
    
    使用方式：
    ```python
    limiter = TokenBucketLimiter(rate=10, burst=20)
    await limiter.acquire()
    # 执行请求
    ```
    """
    
    def __init__(
        self,
        rate: float = 10.0,
        burst: int = 20,
    ):
        """
        初始化令牌桶
        
        Args:
            rate: 每秒生成的令牌数
            burst: 桶的最大容量
        """
        self.rate = rate
        self.burst = burst
        self.tokens = float(burst)
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> float:
        """
        获取令牌
        
        Args:
            tokens: 需要的令牌数
        
        Returns:
            等待时间（秒），0 表示无需等待
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now
            
            self.tokens = min(
                self.burst,
                self.tokens + elapsed * self.rate
            )
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return 0.0
            
            needed = tokens - self.tokens
            wait_time = needed / self.rate
            self.tokens = 0
            
            return wait_time
    
    async def wait_and_acquire(self, tokens: int = 1) -> None:
        """等待并获取令牌"""
        wait_time = await self.acquire(tokens)
        if wait_time > 0:
            await asyncio.sleep(wait_time)


class SlidingWindowLimiter:
    """
    滑动窗口限流器
    
    特点：
    - 精确控制时间窗口内的请求数
    - 适合有明确 RPM/TPM 限制的 API
    
    使用方式：
    ```python
    limiter = SlidingWindowLimiter(max_requests=100, window_seconds=60)
    await limiter.acquire()
    ```
    """
    
    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: float = 60.0,
    ):
        """
        初始化滑动窗口
        
        Args:
            max_requests: 窗口内最大请求数
            window_seconds: 窗口大小（秒）
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: list = []
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> float:
        """
        尝试获取请求许可
        
        Returns:
            需要等待的时间（秒），0 表示可以立即执行
        """
        async with self._lock:
            now = time.monotonic()
            cutoff = now - self.window_seconds
            
            self.requests = [t for t in self.requests if t > cutoff]
            
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return 0.0
            
            oldest = self.requests[0]
            wait_time = oldest + self.window_seconds - now + 0.001
            
            return max(0, wait_time)
    
    async def wait_and_acquire(self) -> None:
        """等待并获取许可"""
        wait_time = await self.acquire()
        if wait_time > 0:
            await asyncio.sleep(wait_time)
            await self.acquire()


class AdaptiveRateLimiter:
    """
    自适应限流器
    
    特点：
    - 根据服务端响应自动调整速率
    - 检测 429 错误自动降速
    - 成功后逐步恢复速率
    
    使用方式：
    ```python
    limiter = AdaptiveRateLimiter(
        initial_rate=10,
        min_rate=1,
        max_rate=50
    )
    await limiter.acquire()
    try:
        response = await make_request()
        limiter.on_success()
    except RateLimitError:
        limiter.on_rate_limited(retry_after=60)
    ```
    """
    
    def __init__(
        self,
        initial_rate: float = 10.0,
        min_rate: float = 1.0,
        max_rate: float = 50.0,
        increase_factor: float = 1.1,
        decrease_factor: float = 0.5,
        cooldown_seconds: float = 5.0,
    ):
        """
        初始化自适应限流器
        
        Args:
            initial_rate: 初始速率（请求/秒）
            min_rate: 最小速率
            max_rate: 最大速率
            increase_factor: 成功后增速因子
            decrease_factor: 限流后降速因子
            cooldown_seconds: 成功后增速冷却时间
        """
        self.current_rate = initial_rate
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.increase_factor = increase_factor
        self.decrease_factor = decrease_factor
        self.cooldown_seconds = cooldown_seconds
        
        self.token_bucket = TokenBucketLimiter(rate=initial_rate, burst=int(initial_rate * 2))
        self.last_success = time.monotonic()
        self.consecutive_successes = 0
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """获取请求许可"""
        await self.token_bucket.wait_and_acquire()
    
    def on_success(self) -> None:
        """请求成功时调用"""
        now = time.monotonic()
        self.last_success = now
        self.consecutive_successes += 1
        
        if self.consecutive_successes >= 5:
            self._increase_rate()
            self.consecutive_successes = 0
    
    def on_rate_limited(self, retry_after: Optional[float] = None) -> None:
        """
        收到 429 限流响应时调用
        
        Args:
            retry_after: 服务端建议的重试等待时间（秒）
        """
        self._decrease_rate()
        self.consecutive_successes = 0
        
        if retry_after:
            logger.warning(
                f"Rate limited, retry after {retry_after}s, "
                f"reducing rate to {self.current_rate:.2f}/s"
            )
    
    def on_error(self, is_server_error: bool = False) -> None:
        """
        请求错误时调用
        
        Args:
            is_server_error: 是否为服务端错误（5xx）
        """
        if is_server_error:
            self._decrease_rate(factor=0.7)
        self.consecutive_successes = 0
    
    def _increase_rate(self) -> None:
        """增加速率"""
        new_rate = min(
            self.max_rate,
            self.current_rate * self.increase_factor
        )
        if new_rate != self.current_rate:
            self.current_rate = new_rate
            self.token_bucket.rate = new_rate
            self.token_bucket.burst = int(new_rate * 2)
            logger.debug(f"Increased rate to {self.current_rate:.2f}/s")
    
    def _decrease_rate(self, factor: Optional[float] = None) -> None:
        """降低速率"""
        factor = factor or self.decrease_factor
        new_rate = max(
            self.min_rate,
            self.current_rate * factor
        )
        self.current_rate = new_rate
        self.token_bucket.rate = new_rate
        self.token_bucket.burst = max(1, int(new_rate * 2))
        logger.info(f"Reduced rate to {self.current_rate:.2f}/s")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "current_rate": round(self.current_rate, 2),
            "min_rate": self.min_rate,
            "max_rate": self.max_rate,
            "consecutive_successes": self.consecutive_successes,
        }


class ConcurrentLimiter:
    """
    并发控制限流器
    
    特点：
    - 限制同时进行的请求数
    - 使用信号量实现
    - 防止并发过高触发限流
    
    使用方式：
    ```python
    limiter = ConcurrentLimiter(max_concurrent=10)
    async with limiter:
        response = await make_request()
    ```
    """
    
    def __init__(self, max_concurrent: int = 10):
        """
        初始化并发限制器
        
        Args:
            max_concurrent: 最大并发数
        """
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_count = 0
        self._lock = asyncio.Lock()
    
    async def __aenter__(self):
        await self._semaphore.acquire()
        async with self._lock:
            self._active_count += 1
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        async with self._lock:
            self._active_count -= 1
        self._semaphore.release()
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "max_concurrent": self.max_concurrent,
            "active_count": self._active_count,
            "available": self._semaphore._value,
        }


class CompositeRateLimiter:
    """
    组合限流器
    
    组合多种限流策略：
    1. 并发控制 - 限制同时请求数
    2. 速率限制 - 控制请求频率
    3. 自适应调整 - 根据响应动态调整
    
    使用方式：
    ```python
    limiter = CompositeRateLimiter(
        requests_per_second=10,
        max_concurrent=5,
        enable_adaptive=True
    )
    
    async with limiter:
        try:
            response = await make_request()
            limiter.on_success()
        except RateLimitError as e:
            limiter.on_rate_limited(e.retry_after)
    """
    
    def __init__(
        self,
        requests_per_second: float = 10.0,
        max_concurrent: int = 10,
        burst_size: Optional[int] = None,
        enable_adaptive: bool = True,
        min_rate: float = 1.0,
        max_rate: float = 50.0,
    ):
        """
        初始化组合限流器
        
        Args:
            requests_per_second: 初始请求速率
            max_concurrent: 最大并发数
            burst_size: 突发大小，默认为速率的 2 倍
            enable_adaptive: 是否启用自适应调整
            min_rate: 最小速率（自适应模式）
            max_rate: 最大速率（自适应模式）
        """
        burst_size = burst_size or int(requests_per_second * 2)
        
        self.concurrent_limiter = ConcurrentLimiter(max_concurrent)
        
        if enable_adaptive:
            self.rate_limiter = AdaptiveRateLimiter(
                initial_rate=requests_per_second,
                min_rate=min_rate,
                max_rate=max_rate,
            )
        else:
            self.rate_limiter = TokenBucketLimiter(
                rate=requests_per_second,
                burst=burst_size,
            )
        
        self.enable_adaptive = enable_adaptive
        self._total_requests = 0
        self._total_rate_limited = 0
        self._total_errors = 0
    
    async def acquire(self) -> None:
        """获取请求许可"""
        if isinstance(self.rate_limiter, AdaptiveRateLimiter):
            await self.rate_limiter.acquire()
        else:
            await self.rate_limiter.wait_and_acquire()
        self._total_requests += 1
    
    async def __aenter__(self):
        await self.acquire()
        await self.concurrent_limiter.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.concurrent_limiter.__aexit__(exc_type, exc_val, exc_tb)
        return False
    
    def on_success(self) -> None:
        """请求成功时调用"""
        if self.enable_adaptive and isinstance(self.rate_limiter, AdaptiveRateLimiter):
            self.rate_limiter.on_success()
    
    def on_rate_limited(self, retry_after: Optional[float] = None) -> None:
        """收到 429 响应时调用"""
        self._total_rate_limited += 1
        if self.enable_adaptive and isinstance(self.rate_limiter, AdaptiveRateLimiter):
            self.rate_limiter.on_rate_limited(retry_after)
    
    def on_error(self, is_server_error: bool = False) -> None:
        """请求错误时调用"""
        self._total_errors += 1
        if self.enable_adaptive and isinstance(self.rate_limiter, AdaptiveRateLimiter):
            self.rate_limiter.on_error(is_server_error)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "total_requests": self._total_requests,
            "total_rate_limited": self._total_rate_limited,
            "total_errors": self._total_errors,
            "concurrent": self.concurrent_limiter.get_stats(),
        }
        if isinstance(self.rate_limiter, AdaptiveRateLimiter):
            stats["rate"] = self.rate_limiter.get_stats()
        return stats


def create_limiter_for_provider(
    provider: str,
    custom_config: Optional[Dict[str, Any]] = None,
) -> CompositeRateLimiter:
    """
    为不同 LLM 提供商创建预设限流器
    
    Args:
        provider: 提供商名称 (openai, anthropic, gemini, etc.)
        custom_config: 自定义配置覆盖默认值
    
    Returns:
        配置好的限流器
    """
    presets = {
        "openai": {
            "requests_per_second": 10.0,
            "max_concurrent": 10,
            "min_rate": 1.0,
            "max_rate": 30.0,
        },
        "anthropic": {
            "requests_per_second": 5.0,
            "max_concurrent": 5,
            "min_rate": 0.5,
            "max_rate": 20.0,
        },
        "gemini": {
            "requests_per_second": 15.0,
            "max_concurrent": 15,
            "min_rate": 1.0,
            "max_rate": 50.0,
        },
        "deepseek": {
            "requests_per_second": 8.0,
            "max_concurrent": 8,
            "min_rate": 0.5,
            "max_rate": 30.0,
        },
        "tavily": {
            "requests_per_second": 10.0,
            "max_concurrent": 10,
            "min_rate": 1.0,
            "max_rate": 30.0,
        },
        "notion": {
            "requests_per_second": 3.0,
            "max_concurrent": 5,
            "min_rate": 0.5,
            "max_rate": 10.0,
        },
        "github": {
            "requests_per_second": 5.0,
            "max_concurrent": 8,
            "min_rate": 0.5,
            "max_rate": 20.0,
        },
        "default": {
            "requests_per_second": 10.0,
            "max_concurrent": 10,
            "min_rate": 1.0,
            "max_rate": 50.0,
        },
    }
    
    config = presets.get(provider.lower(), presets["default"])
    if custom_config:
        config.update(custom_config)
    
    return CompositeRateLimiter(**config)

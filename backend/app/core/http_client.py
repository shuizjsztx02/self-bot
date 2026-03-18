"""
全局 HTTP 客户端管理器

功能：
1. 全局单例模式，应用启动时初始化
2. 连接池管理，连接复用
3. 多客户端支持（默认客户端 + 专用客户端）
4. 统一配置（超时、重试、代理等）
5. 监控统计（成功率、延迟等）
6. 限流控制（令牌桶、自适应）
7. 优雅关闭
"""

import asyncio
import time
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
import httpx
from app.config import settings
import logging

from app.core.rate_limiter import (
    CompositeRateLimiter,
    create_limiter_for_provider,
)

logger = logging.getLogger(__name__)


class HTTPClientStats:
    """HTTP 客户端统计信息"""
    
    def __init__(self):
        self.total_requests = 0
        self.success_requests = 0
        self.failed_requests = 0
        self.total_latency_ms = 0.0
        self.max_latency_ms = 0.0
        self.min_latency_ms = float('inf')
    
    def record_request(self, success: bool, latency_ms: float):
        """记录请求"""
        self.total_requests += 1
        if success:
            self.success_requests += 1
        else:
            self.failed_requests += 1
        
        self.total_latency_ms += latency_ms
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)
        self.min_latency_ms = min(self.min_latency_ms, latency_ms)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        avg_latency = (
            self.total_latency_ms / self.total_requests 
            if self.total_requests > 0 else 0
        )
        
        return {
            "total_requests": self.total_requests,
            "success_requests": self.success_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (
                self.success_requests / self.total_requests * 100
                if self.total_requests > 0 else 0
            ),
            "avg_latency_ms": round(avg_latency, 2),
            "max_latency_ms": round(self.max_latency_ms, 2),
            "min_latency_ms": round(self.min_latency_ms if self.min_latency_ms != float('inf') else 0, 2),
        }


class HTTPClientManager:
    """
    全局 HTTP 客户端管理器
    
    使用方式：
    ```python
    # 获取默认客户端
    client = await HTTPClientManager.get_client()
    
    # 获取专用客户端
    client = await HTTPClientManager.get_client("tavily")
    
    # 使用上下文管理器
    async with HTTPClientManager.request_context() as client:
        response = await client.get("https://example.com")
    ```
    """
    
    _instance: Optional['HTTPClientManager'] = None
    _lock = asyncio.Lock()
    
    def __init__(self):
        self._default_client: Optional[httpx.AsyncClient] = None
        self._specialized_clients: Dict[str, httpx.AsyncClient] = {}
        self._stats: Dict[str, HTTPClientStats] = {}
        self._rate_limiters: Dict[str, CompositeRateLimiter] = {}
        self._initialized = False
    
    @classmethod
    async def get_instance(cls) -> 'HTTPClientManager':
        """获取单例实例"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    await cls._instance.initialize()
        return cls._instance
    
    async def initialize(self):
        """初始化客户端管理器"""
        if self._initialized:
            return
        
        logger.info("Initializing HTTP Client Manager...")
        
        self._default_client = await self._create_default_client()
        self._stats["default"] = HTTPClientStats()
        self._rate_limiters["default"] = CompositeRateLimiter(
            requests_per_second=getattr(settings, 'HTTP_RATE_LIMIT', 20.0),
            max_concurrent=getattr(settings, 'HTTP_MAX_CONCURRENT', 20),
            enable_adaptive=getattr(settings, 'HTTP_ADAPTIVE_RATE_LIMIT', True),
        )
        
        await self._create_specialized_clients()
        
        self._initialized = True
        logger.info("HTTP Client Manager initialized successfully")
    
    async def _create_default_client(self) -> httpx.AsyncClient:
        """创建默认客户端"""
        return httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=getattr(settings, 'HTTP_CONNECT_TIMEOUT', 5.0),
                read=getattr(settings, 'HTTP_READ_TIMEOUT', 30.0),
                write=getattr(settings, 'HTTP_WRITE_TIMEOUT', 10.0),
                pool=getattr(settings, 'HTTP_POOL_TIMEOUT', 5.0),
            ),
            limits=httpx.Limits(
                max_connections=getattr(settings, 'HTTP_MAX_CONNECTIONS', 100),
                max_keepalive_connections=getattr(settings, 'HTTP_MAX_KEEPALIVE_CONNECTIONS', 20),
                keepalive_expiry=getattr(settings, 'HTTP_KEEPALIVE_EXPIRY', 30.0),
            ),
            http2=getattr(settings, 'HTTP_ENABLE_HTTP2', True),
            follow_redirects=True,
            verify=True,
        )
    
    async def _create_specialized_clients(self):
        """创建专用客户端"""
        if hasattr(settings, 'TAVILY_API_KEY') and settings.TAVILY_API_KEY:
            self._specialized_clients["tavily"] = httpx.AsyncClient(
                base_url="https://api.tavily.com",
                timeout=httpx.Timeout(timeout=30.0, connect=5.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
                headers={
                    "Authorization": f"Bearer {settings.TAVILY_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            self._stats["tavily"] = HTTPClientStats()
            self._rate_limiters["tavily"] = create_limiter_for_provider("tavily")
            logger.info("Created specialized client: tavily")
        
        if hasattr(settings, 'NOTION_API_KEY') and settings.NOTION_API_KEY:
            self._specialized_clients["notion"] = httpx.AsyncClient(
                base_url="https://api.notion.com/v1",
                timeout=httpx.Timeout(timeout=30.0, connect=5.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
                headers={
                    "Authorization": f"Bearer {settings.NOTION_API_KEY}",
                    "Notion-Version": "2022-06-28",
                    "Content-Type": "application/json",
                },
            )
            self._stats["notion"] = HTTPClientStats()
            self._rate_limiters["notion"] = create_limiter_for_provider("notion")
            logger.info("Created specialized client: notion")
        
        if hasattr(settings, 'GITHUB_TOKEN') and settings.GITHUB_TOKEN:
            self._specialized_clients["github"] = httpx.AsyncClient(
                base_url="https://api.github.com",
                timeout=httpx.Timeout(timeout=30.0, connect=5.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
                headers={
                    "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            self._stats["github"] = HTTPClientStats()
            self._rate_limiters["github"] = create_limiter_for_provider("github")
            logger.info("Created specialized client: github")
        
        if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
            self._rate_limiters["openai"] = create_limiter_for_provider("openai")
            logger.info("Created rate limiter: openai")
        
        if hasattr(settings, 'ANTHROPIC_API_KEY') and settings.ANTHROPIC_API_KEY:
            self._rate_limiters["anthropic"] = create_limiter_for_provider("anthropic")
            logger.info("Created rate limiter: anthropic")
    
    @classmethod
    async def get_client(cls, name: str = "default") -> httpx.AsyncClient:
        """
        获取 HTTP 客户端
        
        Args:
            name: 客户端名称，"default" 或专用客户端名称
        
        Returns:
            httpx.AsyncClient 实例
        """
        instance = await cls.get_instance()
        
        if name == "default":
            return instance._default_client
        elif name in instance._specialized_clients:
            return instance._specialized_clients[name]
        else:
            logger.warning(f"Client '{name}' not found, using default client")
            return instance._default_client
    
    @classmethod
    @asynccontextmanager
    async def request_context(cls, name: str = "default"):
        """
        请求上下文管理器
        
        使用方式：
        ```python
        async with HTTPClientManager.request_context("tavily") as client:
            response = await client.post("/search", json={...})
        ```
        """
        client = await cls.get_client(name)
        start_time = time.time()
        success = False
        
        try:
            yield client
            success = True
        finally:
            latency_ms = (time.time() - start_time) * 1000
            instance = await cls.get_instance()
            if name in instance._stats:
                instance._stats[name].record_request(success, latency_ms)
    
    @classmethod
    async def request(
        cls,
        method: str,
        url: str,
        client_name: str = "default",
        rate_limit: bool = True,
        **kwargs
    ) -> httpx.Response:
        """
        发送 HTTP 请求（带自动重试和限流）
        
        Args:
            method: HTTP 方法 (GET, POST, PUT, DELETE, etc.)
            url: 请求 URL
            client_name: 客户端名称
            rate_limit: 是否启用限流
            **kwargs: 其他请求参数
        
        Returns:
            httpx.Response 响应对象
        
        Raises:
            httpx.HTTPError: 请求失败
        """
        instance = await cls.get_instance()
        client = await cls.get_client(client_name)
        
        limiter = instance._rate_limiters.get(client_name) if rate_limit else None
        
        if limiter:
            await limiter.acquire()
        
        start_time = time.time()
        success = False
        max_retries = getattr(settings, 'HTTP_MAX_RETRIES', 3)
        retry_delay = getattr(settings, 'HTTP_RETRY_DELAY', 1.0)
        
        last_error = None
        for attempt in range(max_retries):
            try:
                response = await client.request(method, url, **kwargs)
                
                if response.status_code == 429:
                    retry_after = None
                    if "retry-after" in response.headers:
                        try:
                            retry_after = float(response.headers["retry-after"])
                        except ValueError:
                            pass
                    
                    if limiter:
                        limiter.on_rate_limited(retry_after)
                    
                    if attempt < max_retries - 1:
                        wait_time = retry_after or (retry_delay * (2 ** attempt))
                        logger.warning(
                            f"Rate limited (429), waiting {wait_time}s before retry "
                            f"(attempt {attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                
                response.raise_for_status()
                success = True
                
                if limiter:
                    limiter.on_success()
                
                return response
                
            except httpx.HTTPStatusError as e:
                if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                    latency_ms = (time.time() - start_time) * 1000
                    if client_name in instance._stats:
                        instance._stats[client_name].record_request(False, latency_ms)
                    raise
                
                is_server_error = e.response.status_code >= 500
                if limiter:
                    limiter.on_error(is_server_error)
                
                last_error = e
                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{max_retries}): {e}"
                )
            except httpx.RequestError as e:
                if limiter:
                    limiter.on_error(is_server_error=False)
                last_error = e
                logger.warning(
                    f"Request error (attempt {attempt + 1}/{max_retries}): {e}"
                )
            
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))
        
        latency_ms = (time.time() - start_time) * 1000
        if client_name in instance._stats:
            instance._stats[client_name].record_request(False, latency_ms)
        
        raise last_error or httpx.HTTPError("Request failed after retries")
    
    @classmethod
    async def get(cls, url: str, client_name: str = "default", **kwargs) -> httpx.Response:
        """发送 GET 请求"""
        return await cls.request("GET", url, client_name, **kwargs)
    
    @classmethod
    async def post(cls, url: str, client_name: str = "default", **kwargs) -> httpx.Response:
        """发送 POST 请求"""
        return await cls.request("POST", url, client_name, **kwargs)
    
    @classmethod
    async def put(cls, url: str, client_name: str = "default", **kwargs) -> httpx.Response:
        """发送 PUT 请求"""
        return await cls.request("PUT", url, client_name, **kwargs)
    
    @classmethod
    async def delete(cls, url: str, client_name: str = "default", **kwargs) -> httpx.Response:
        """发送 DELETE 请求"""
        return await cls.request("DELETE", url, client_name, **kwargs)
    
    @classmethod
    async def get_stats(cls, name: str = "default") -> Dict[str, Any]:
        """获取客户端统计信息"""
        instance = await cls.get_instance()
        stats = {}
        if name in instance._stats:
            stats = instance._stats[name].get_stats()
        if name in instance._rate_limiters:
            stats["rate_limiter"] = instance._rate_limiters[name].get_stats()
        return stats
    
    @classmethod
    async def get_all_stats(cls) -> Dict[str, Dict[str, Any]]:
        """获取所有客户端统计信息"""
        instance = await cls.get_instance()
        result = {}
        for name, stats in instance._stats.items():
            result[name] = stats.get_stats()
            if name in instance._rate_limiters:
                result[name]["rate_limiter"] = instance._rate_limiters[name].get_stats()
        return result
    
    @classmethod
    async def get_rate_limiter(cls, name: str = "default") -> Optional[CompositeRateLimiter]:
        """获取限流器"""
        instance = await cls.get_instance()
        return instance._rate_limiters.get(name)
    
    @classmethod
    async def with_rate_limit(cls, name: str = "default"):
        """
        带限流的请求上下文管理器
        
        使用方式：
        ```python
        async with HTTPClientManager.with_rate_limit("openai") as limiter:
            # limiter 会自动控制请求速率
            response = await make_openai_request()
            limiter.on_success()
        ```
        """
        instance = await cls.get_instance()
        limiter = instance._rate_limiters.get(name)
        if limiter:
            return limiter
        return instance._rate_limiters.get("default")
    
    @classmethod
    async def close(cls):
        """关闭所有客户端"""
        instance = await cls.get_instance()
        
        logger.info("Closing HTTP clients...")
        
        if instance._default_client:
            await instance._default_client.aclose()
            instance._default_client = None
        
        for name, client in instance._specialized_clients.items():
            await client.aclose()
            logger.info(f"Closed client: {name}")
        
        instance._specialized_clients.clear()
        instance._initialized = False
        
        logger.info("All HTTP clients closed")


async def get_http_client(name: str = "default") -> httpx.AsyncClient:
    """获取 HTTP 客户端（便捷函数）"""
    return await HTTPClientManager.get_client(name)


async def http_get(url: str, client_name: str = "default", **kwargs) -> httpx.Response:
    """发送 GET 请求（便捷函数）"""
    return await HTTPClientManager.get(url, client_name, **kwargs)


async def http_post(url: str, client_name: str = "default", **kwargs) -> httpx.Response:
    """发送 POST 请求（便捷函数）"""
    return await HTTPClientManager.post(url, client_name, **kwargs)


async def http_put(url: str, client_name: str = "default", **kwargs) -> httpx.Response:
    """发送 PUT 请求（便捷函数）"""
    return await HTTPClientManager.put(url, client_name, **kwargs)


async def http_delete(url: str, client_name: str = "default", **kwargs) -> httpx.Response:
    """发送 DELETE 请求（便捷函数）"""
    return await HTTPClientManager.delete(url, client_name, **kwargs)

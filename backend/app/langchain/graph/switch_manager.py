"""
切换管理器

管理新旧架构之间的切换，支持灰度发布和回滚
"""
import os
import logging
import hashlib
import random
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime
from functools import wraps

from app.langchain.graph.feature_flags import GraphFeatureFlags

logger = logging.getLogger(__name__)


class SwitchManager:
    """
    切换管理器
    
    管理新旧架构的切换，支持：
    - 全量切换
    - 灰度发布（按用户 ID）
    - 流量比例控制
    - 自动回滚
    """
    
    def __init__(self):
        self._switch_history: List[Dict[str, Any]] = []
        self._rollback_handlers: List[Callable] = []
        self._metrics: Dict[str, Any] = {
            "new_arch_requests": 0,
            "old_arch_requests": 0,
            "new_arch_errors": 0,
            "old_arch_errors": 0,
        }
    
    def should_use_new_arch(self, user_id: Optional[str] = None) -> bool:
        """
        判断是否应该使用新架构
        
        Args:
            user_id: 用户 ID（用于灰度）
            
        Returns:
            是否使用新架构
        """
        if not GraphFeatureFlags.USE_LANGGRAPH:
            self._metrics["old_arch_requests"] += 1
            return False
        
        ratio = GraphFeatureFlags.LANGGRAPH_TRAFFIC_RATIO
        
        if ratio >= 1.0:
            self._metrics["new_arch_requests"] += 1
            return True
        
        if ratio <= 0.0:
            self._metrics["old_arch_requests"] += 1
            return False
        
        if user_id:
            hash_value = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
            use_new = (hash_value % 100) < (ratio * 100)
        else:
            use_new = random.random() < ratio
        
        if use_new:
            self._metrics["new_arch_requests"] += 1
        else:
            self._metrics["old_arch_requests"] += 1
        
        return use_new
    
    def record_result(self, use_new_arch: bool, success: bool, duration_ms: float):
        """
        记录执行结果
        
        Args:
            use_new_arch: 是否使用了新架构
            success: 是否成功
            duration_ms: 执行时长（毫秒）
        """
        if use_new_arch:
            if not success:
                self._metrics["new_arch_errors"] += 1
        else:
            if not success:
                self._metrics["old_arch_errors"] += 1
    
    def switch_to_new(self, reason: str = "Manual switch"):
        """
        切换到新架构
        
        Args:
            reason: 切换原因
        """
        GraphFeatureFlags.enable_langgraph()
        GraphFeatureFlags.set_traffic_ratio(1.0)
        
        self._record_switch("new", reason)
        logger.info(f"[SwitchManager] Switched to new architecture: {reason}")
    
    def switch_to_old(self, reason: str = "Manual switch"):
        """
        切换到旧架构
        
        Args:
            reason: 切换原因
        """
        GraphFeatureFlags.disable_langgraph()
        GraphFeatureFlags.set_traffic_ratio(0.0)
        
        self._record_switch("old", reason)
        logger.info(f"[SwitchManager] Switched to old architecture: {reason}")
    
    def rollback(self, reason: str = "Rollback"):
        """
        回滚到旧架构
        
        Args:
            reason: 回滚原因
        """
        self.switch_to_old(reason)
        
        for handler in self._rollback_handlers:
            try:
                handler()
            except Exception as e:
                logger.error(f"[SwitchManager] Rollback handler error: {e}")
    
    def set_traffic_ratio(self, ratio: float, reason: str = "Traffic adjustment"):
        """
        设置流量比例
        
        Args:
            ratio: 流量比例 (0.0 - 1.0)
            reason: 调整原因
        """
        GraphFeatureFlags.set_traffic_ratio(ratio)
        self._record_switch(f"ratio={ratio}", reason)
        logger.info(f"[SwitchManager] Traffic ratio set to {ratio:.2%}: {reason}")
    
    def register_rollback_handler(self, handler: Callable):
        """
        注册回滚处理器
        
        Args:
            handler: 回滚时执行的函数
        """
        self._rollback_handlers.append(handler)
    
    def _record_switch(self, target: str, reason: str):
        """记录切换历史"""
        self._switch_history.append({
            "target": target,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        })
    
    def get_switch_history(self) -> List[Dict[str, Any]]:
        """获取切换历史"""
        return self._switch_history.copy()
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取指标"""
        return self._metrics.copy()


_switch_manager = SwitchManager()


def get_switch_manager() -> SwitchManager:
    """获取全局切换管理器"""
    return _switch_manager


def with_architecture_switch(func: Callable) -> Callable:
    """
    架构切换装饰器
    
    根据功能开关自动选择新旧架构
    
    Usage:
        @with_architecture_switch
        async def process_request(query, user_id=None):
            # 新架构实现
            return result
        
        @process_request.fallback
        async def process_request_old(query, user_id=None):
            # 旧架构实现
            return result
    """
    fallback_func = None
    
    @wraps(func)
    async def wrapper(*args, **kwargs):
        user_id = kwargs.get("user_id")
        switch_manager = get_switch_manager()
        
        use_new = switch_manager.should_use_new_arch(user_id)
        
        start_time = datetime.now()
        
        try:
            if use_new:
                result = await func(*args, **kwargs)
            elif fallback_func:
                result = await fallback_func(*args, **kwargs)
            else:
                result = await func(*args, **kwargs)
            
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            switch_manager.record_result(use_new, True, duration_ms)
            
            return result
            
        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            switch_manager.record_result(use_new, False, duration_ms)
            
            if use_new and fallback_func:
                logger.warning(f"[with_architecture_switch] New arch failed, falling back: {e}")
                return await fallback_func(*args, **kwargs)
            
            raise
    
    def set_fallback(f: Callable):
        nonlocal fallback_func
        fallback_func = f
        return f
    
    wrapper.fallback = set_fallback
    
    return wrapper

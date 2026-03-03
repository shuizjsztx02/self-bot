"""
LangGraph 功能开关

控制新旧架构的切换
"""
import os
from typing import Optional
from functools import wraps
import logging

logger = logging.getLogger(__name__)

try:
    from app.config import settings
    _default_use_langgraph = settings.USE_LANGGRAPH
    _default_parallel = settings.LANGGRAPH_PARALLEL
    _default_ratio = settings.LANGGRAPH_TRAFFIC_RATIO
except ImportError:
    _default_use_langgraph = False
    _default_parallel = False
    _default_ratio = 0.0


class GraphFeatureFlags:
    """
    图功能开关
    
    通过环境变量或配置控制新旧实现切换
    
    使用方式:
        # 环境变量
        export USE_LANGGRAPH=true
        
        # 代码中
        GraphFeatureFlags.enable_langgraph()
        GraphFeatureFlags.disable_langgraph()
        
        # 检查状态
        if GraphFeatureFlags.USE_LANGGRAPH:
            # 使用新架构
        else:
            # 使用旧架构
    """
    
    USE_LANGGRAPH: bool = os.getenv("USE_LANGGRAPH", str(_default_use_langgraph)).lower() == "true"
    LANGGRAPH_PARALLEL: bool = os.getenv("LANGGRAPH_PARALLEL", str(_default_parallel)).lower() == "true"
    LANGGRAPH_TRAFFIC_RATIO: float = float(os.getenv("LANGGRAPH_TRAFFIC_RATIO", str(_default_ratio)))
    
    @staticmethod
    def enable_langgraph():
        """启用 LangGraph"""
        os.environ["USE_LANGGRAPH"] = "true"
        GraphFeatureFlags.USE_LANGGRAPH = True
        logger.info("[GraphFeatureFlags] LangGraph enabled")
    
    @staticmethod
    def disable_langgraph():
        """禁用 LangGraph (回滚)"""
        os.environ["USE_LANGGRAPH"] = "false"
        GraphFeatureFlags.USE_LANGGRAPH = False
        logger.info("[GraphFeatureFlags] LangGraph disabled")
    
    @staticmethod
    def enable_parallel():
        """启用并行执行"""
        os.environ["LANGGRAPH_PARALLEL"] = "true"
        GraphFeatureFlags.LANGGRAPH_PARALLEL = True
        logger.info("[GraphFeatureFlags] Parallel execution enabled")
    
    @staticmethod
    def disable_parallel():
        """禁用并行执行"""
        os.environ["LANGGRAPH_PARALLEL"] = "false"
        GraphFeatureFlags.LANGGRAPH_PARALLEL = False
        logger.info("[GraphFeatureFlags] Parallel execution disabled")
    
    @staticmethod
    def set_traffic_ratio(ratio: float):
        """
        设置流量比例
        
        Args:
            ratio: 0.0 - 1.0 之间的值
        """
        ratio = max(0.0, min(1.0, ratio))
        os.environ["LANGGRAPH_TRAFFIC_RATIO"] = str(ratio)
        GraphFeatureFlags.LANGGRAPH_TRAFFIC_RATIO = ratio
        logger.info(f"[GraphFeatureFlags] Traffic ratio set to {ratio:.2%}")
    
    @staticmethod
    def should_use_langgraph(user_id: Optional[str] = None) -> bool:
        """
        判断是否应该使用 LangGraph
        
        考虑全局开关和流量比例
        
        Args:
            user_id: 用户 ID (可用于灰度)
            
        Returns:
            是否使用 LangGraph
        """
        if not GraphFeatureFlags.USE_LANGGRAPH:
            return False
        
        if GraphFeatureFlags.LANGGRAPH_TRAFFIC_RATIO >= 1.0:
            return True
        
        if GraphFeatureFlags.LANGGRAPH_TRAFFIC_RATIO <= 0.0:
            return False
        
        import hashlib
        if user_id:
            hash_value = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
            return (hash_value % 100) < (GraphFeatureFlags.LANGGRAPH_TRAFFIC_RATIO * 100)
        
        import random
        return random.random() < GraphFeatureFlags.LANGGRAPH_TRAFFIC_RATIO
    
    @staticmethod
    def get_status() -> dict:
        """
        获取当前状态
        
        Returns:
            状态字典
        """
        return {
            "use_langgraph": GraphFeatureFlags.USE_LANGGRAPH,
            "parallel_enabled": GraphFeatureFlags.LANGGRAPH_PARALLEL,
            "traffic_ratio": GraphFeatureFlags.LANGGRAPH_TRAFFIC_RATIO,
        }


def with_langgraph_fallback(func):
    """
    装饰器: 自动处理 LangGraph 和旧架构的切换
    
    如果 LangGraph 启用且执行失败，自动回退到旧架构
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        if not GraphFeatureFlags.USE_LANGGRAPH:
            return await func(*args, **kwargs)
        
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"[with_langgraph_fallback] LangGraph failed, falling back: {e}")
            GraphFeatureFlags.disable_langgraph()
            try:
                return await func(*args, **kwargs)
            finally:
                GraphFeatureFlags.enable_langgraph()
    
    return wrapper

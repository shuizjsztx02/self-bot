"""
LangGraph 服务层

提供与现有 API 兼容的接口，内部使用 LangGraph 架构
"""
import logging
from typing import Dict, Any, Optional, AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession

from app.langchain.graph import (
    SupervisorGraphRunner,
    get_switch_manager,
    GraphFeatureFlags,
)
from app.langchain.graph.state import create_initial_state

logger = logging.getLogger(__name__)


class LangGraphService:
    """
    LangGraph 服务
    
    提供与现有 Agent 接口兼容的方法，内部使用 LangGraph 图
    """
    
    def __init__(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        db_session: Optional[AsyncSession] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.conversation_id = conversation_id
        self.user_id = user_id
        self.db_session = db_session
        self.provider = provider
        self.model = model
        self._runner = SupervisorGraphRunner(use_full_graph=True)
    
    async def chat(self, message: str, db: Optional[AsyncSession] = None) -> Dict[str, Any]:
        """
        同步聊天接口
        
        Args:
            message: 用户消息
            db: 数据库会话
            
        Returns:
            包含 output 和 tool_calls 的字典
        """
        db = db or self.db_session
        
        logger.info(f"[LangGraphService] Processing chat: {message[:50]}...")
        
        try:
            result = await self._runner.run(
                query=message,
                user_id=self.user_id,
                conversation_id=self.conversation_id,
                db_session=db,
            )
            
            output = result.get("final_response", "")
            tool_calls = result.get("tool_calls", [])
            
            if result.get("error"):
                logger.warning(f"[LangGraphService] Graph error: {result.get('error')}")
                if not output:
                    output = f"处理请求时发生错误: {result.get('error')}"
            
            return {
                "output": output,
                "tool_calls": tool_calls,
                "intent": result.get("intent"),
                "confidence": result.get("confidence"),
                "node_executions": result.get("node_executions", []),
            }
            
        except Exception as e:
            logger.error(f"[LangGraphService] Chat error: {e}")
            return {
                "output": f"抱歉，处理请求时发生错误: {str(e)}",
                "tool_calls": [],
                "error": str(e),
            }
    
    async def chat_stream(
        self,
        message: str,
        db: Optional[AsyncSession] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        流式聊天接口
        
        Args:
            message: 用户消息
            db: 数据库会话
            
        Yields:
            SSE 格式的响应片段
        """
        import json
        from datetime import datetime, timezone
        
        db = db or self.db_session
        
        logger.info(f"[LangGraphService] Processing stream chat: {message[:50]}...")
        
        try:
            async for event in self._runner.stream(
                query=message,
                user_id=self.user_id,
                conversation_id=self.conversation_id,
                db_session=db,
            ):
                for node_name, node_output in event.items():
                    if isinstance(node_output, dict):
                        if "final_response" in node_output and node_output["final_response"]:
                            data = {
                                "type": "content",
                                "content": node_output["final_response"],
                                "node": node_name,
                            }
                            yield data
                        
                        if "stream_chunk" in node_output:
                            data = {
                                "type": "chunk",
                                "content": node_output["stream_chunk"],
                                "node": node_name,
                            }
                            yield data
            
            data = {
                "type": "done",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            yield data
            
        except Exception as e:
            logger.error(f"[LangGraphService] Stream error: {e}")
            data = {
                "type": "error",
                "error": str(e),
            }
            yield data


def should_use_langgraph() -> bool:
    """
    判断是否应该使用 LangGraph 架构
    
    Returns:
        是否使用 LangGraph
    """
    return GraphFeatureFlags.USE_LANGGRAPH


async def get_agent(
    conversation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    db_session: Optional[AsyncSession] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    use_langgraph: Optional[bool] = None,
):
    """
    获取 Agent 实例
    
    根据配置返回旧架构或新架构的 Agent
    
    Args:
        conversation_id: 会话 ID
        user_id: 用户 ID
        db_session: 数据库会话
        provider: LLM 提供商
        model: 模型名称
        use_langgraph: 是否使用 LangGraph (None 时自动判断)
        
    Returns:
        Agent 实例
    """
    if use_langgraph is None:
        use_langgraph = should_use_langgraph()
    
    if use_langgraph:
        logger.info("[AgentFactory] Using LangGraph architecture")
        return LangGraphService(
            conversation_id=conversation_id,
            user_id=user_id,
            db_session=db_session,
            provider=provider,
            model=model,
        )
    else:
        logger.info("[AgentFactory] Using legacy architecture")
        from app.langchain.agents.supervisor_agent import SupervisorAgent
        return SupervisorAgent(
            conversation_id=conversation_id,
            user_id=user_id,
            db_session=db_session,
        )

"""
主 Agent 节点

包装现有 MainAgent，提供 LangGraph 兼容的节点函数
"""
import time
import logging
from typing import Dict, Any, Optional, AsyncIterator

from app.langchain.graph.state import SupervisorState, StateAdapter
from app.langchain.graph.adapters.main_adapter import MainAgentAdapter

logger = logging.getLogger(__name__)


async def generate_response_node(state: SupervisorState) -> Dict[str, Any]:
    """
    响应生成节点
    
    使用 MainAgent 生成最终响应
    
    Args:
        state: 当前状态
        
    Returns:
        更新后的状态片段
    """
    start_time = time.time()
    query = state.get("query", "")
    user_id = state.get("user_id")
    conversation_id = state.get("conversation_id")
    db_session = state.get("db_session")
    
    logger.info(f"[MainNode] Generating response for: {query[:50]}...")
    
    try:
        from app.langchain.agents.main_agent import MainAgent
        
        agent = MainAgent(
            conversation_id=conversation_id,
            user_name=user_id or "用户",
        )
        
        enhanced_query = MainAgentAdapter.build_enhanced_query(state)
        
        result = await agent.chat(enhanced_query, db=db_session)
        
        update = MainAgentAdapter.to_state(result, dict(state))
        
        duration_ms = (time.time() - start_time) * 1000
        
        state = StateAdapter.record_node_execution(
            state,
            node_name="generate_response",
            success=True,
            duration_ms=duration_ms,
        )
        update["node_executions"] = state.get("node_executions", [])
        
        logger.info(f"[MainNode] Response generated (duration={duration_ms:.1f}ms)")
        
        return update
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"[MainNode] Error: {e}")
        
        state = StateAdapter.record_node_execution(
            state,
            node_name="generate_response",
            success=False,
            duration_ms=duration_ms,
            error=str(e),
        )
        
        return {
            "final_response": "",
            "error": str(e),
            "error_node": "generate_response",
            "node_executions": state.get("node_executions", []),
        }


async def generate_response_stream_node(
    state: SupervisorState,
) -> AsyncIterator[Dict[str, Any]]:
    """
    流式响应生成节点
    
    使用 MainAgent 生成流式响应
    
    Args:
        state: 当前状态
        
    Yields:
        响应片段
    """
    start_time = time.time()
    query = state.get("query", "")
    user_id = state.get("user_id")
    conversation_id = state.get("conversation_id")
    db_session = state.get("db_session")
    
    logger.info(f"[MainStreamNode] Streaming response for: {query[:50]}...")
    
    try:
        from app.langchain.agents.main_agent import MainAgent
        
        agent = MainAgent(
            conversation_id=conversation_id,
            user_name=user_id or "用户",
        )
        
        enhanced_query = MainAgentAdapter.build_enhanced_query(state)
        
        full_response = ""
        async for chunk in agent.chat_stream(enhanced_query, db=db_session):
            if isinstance(chunk, dict):
                if chunk.get("type") == "content":
                    content = chunk.get("content", "")
                    full_response += content
                    yield {"stream_chunk": content, "final_response": full_response}
            elif isinstance(chunk, str):
                full_response += chunk
                yield {"stream_chunk": chunk, "final_response": full_response}
        
        duration_ms = (time.time() - start_time) * 1000
        
        state = StateAdapter.record_node_execution(
            state,
            node_name="generate_response_stream",
            success=True,
            duration_ms=duration_ms,
        )
        
        yield {
            "final_response": full_response,
            "node_executions": state.get("node_executions", []),
        }
        
        logger.info(f"[MainStreamNode] Stream completed (duration={duration_ms:.1f}ms)")
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"[MainStreamNode] Error: {e}")
        
        state = StateAdapter.record_node_execution(
            state,
            node_name="generate_response_stream",
            success=False,
            duration_ms=duration_ms,
            error=str(e),
        )
        
        yield {
            "final_response": "",
            "error": str(e),
            "error_node": "generate_response_stream",
            "node_executions": state.get("node_executions", []),
        }


async def finalize_node(state: SupervisorState) -> Dict[str, Any]:
    """
    最终化节点
    
    处理收尾工作，如保存记忆、记录日志等
    
    Args:
        state: 当前状态
        
    Returns:
        更新后的状态片段
    """
    start_time = time.time()
    
    logger.info("[FinalizeNode] Finalizing...")
    
    try:
        from datetime import datetime
        
        update = {
            "end_time": datetime.now().isoformat(),
        }
        
        if state.get("error"):
            update["success"] = False
        else:
            update["success"] = True
        
        duration_ms = (time.time() - start_time) * 1000
        
        state = StateAdapter.record_node_execution(
            state,
            node_name="finalize",
            success=True,
            duration_ms=duration_ms,
        )
        update["node_executions"] = state.get("node_executions", [])
        
        logger.info(f"[FinalizeNode] Finalized (success={update['success']})")
        
        return update
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"[FinalizeNode] Error: {e}")
        
        state = StateAdapter.record_node_execution(
            state,
            node_name="finalize",
            success=False,
            duration_ms=duration_ms,
            error=str(e),
        )
        
        return {
            "success": False,
            "error": str(e),
            "node_executions": state.get("node_executions", []),
        }


def format_final_response(state: SupervisorState) -> str:
    """
    格式化最终响应
    
    Args:
        state: 当前状态
        
    Returns:
        格式化后的响应字符串
    """
    response = state.get("final_response", "")
    
    if not response:
        if state.get("error"):
            return f"抱歉，处理过程中出现错误：{state.get('error')}"
        return "抱歉，我无法生成响应。"
    
    return response

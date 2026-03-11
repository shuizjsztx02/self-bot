"""
主 Agent 节点

使用 ChatService 进行对话，提供 LangGraph 兼容的节点函数
支持共享记忆系统（通过 ContextVar 传递）
"""
import time
import logging
from typing import Dict, Any, Optional, AsyncIterator, List

from app.langchain.graph.state import (
    SupervisorState, StateAdapter,
    get_db_session, get_shared_memory,
    get_side_channel,
)
from app.langchain.graph.adapters.main_adapter import MainAgentAdapter

logger = logging.getLogger(__name__)


def _extract_history_from_state(state: SupervisorState) -> List:
    """
    从状态中提取历史消息
    
    Args:
        state: 当前状态
        
    Returns:
        历史消息列表（不包含当前用户消息）
    """
    messages = state.get("messages", [])
    
    if not messages:
        return []
    
    history = []
    for msg in messages[:-1]:
        if hasattr(msg, 'content'):
            history.append(msg)
        elif isinstance(msg, dict) and 'content' in msg:
            from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role == 'user':
                history.append(HumanMessage(content=content))
            elif role == 'assistant':
                history.append(AIMessage(content=content))
            elif role == 'system':
                history.append(SystemMessage(content=content))
    
    return history


async def generate_response_node(state: SupervisorState) -> Dict[str, Any]:
    """
    响应生成节点
    
    使用 ChatService 生成最终响应
    
    Args:
        state: 当前状态
        
    Returns:
        更新后的状态片段
    """
    start_time = time.time()
    query = state.get("query", "")
    user_id = state.get("user_id")
    conversation_id = state.get("conversation_id")
    db_session = get_db_session()
    shared_memory = get_shared_memory()
    selected_tools = state.get("selected_tools")
    
    logger.info(f"[MainNode] Generating response for: {query[:50]}...")
    if selected_tools:
        logger.info(f"[MainNode] Using {len(selected_tools)} pre-selected tools")
    logger.info(f"[MainNode] Has shared_memory: {shared_memory is not None}")
    
    try:
        from app.langchain.services.chat import ChatService
        
        service = ChatService(
            conversation_id=conversation_id,
            user_name=user_id or "用户",
            short_term_memory=shared_memory,
            selected_tools=selected_tools,
        )
        
        history_messages = _extract_history_from_state(state)
        logger.info(f"[MainNode] Extracted {len(history_messages)} history messages from state")
        
        enhanced_query = MainAgentAdapter.build_enhanced_query(state)
        
        result = await service.chat(enhanced_query, db=db_session, history_messages=history_messages)
        
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

    使用 ChatService.chat_stream() 生成流式响应。
    特殊事件（如 skill_dependency_confirm）通过 ContextVar 旁路通道传递，
    绕过 LangGraph 状态机限制。

    Yields:
        仅包含 SupervisorState 兼容字段的状态更新
    """
    start_time = time.time()
    query = state.get("query", "")
    user_id = state.get("user_id")
    conversation_id = state.get("conversation_id")
    db_session = get_db_session()
    shared_memory = get_shared_memory()
    selected_tools = state.get("selected_tools")

    logger.info(f"[MainStreamNode] Streaming response for: {query[:50]}...")
    if selected_tools:
        logger.info(f"[MainStreamNode] Using {len(selected_tools)} pre-selected tools")

    try:
        from app.langchain.services.chat import ChatService

        service = ChatService(
            conversation_id=conversation_id,
            user_name=user_id or "用户",
            short_term_memory=shared_memory,
            selected_tools=selected_tools,
        )

        history_messages = _extract_history_from_state(state)
        enhanced_query = MainAgentAdapter.build_enhanced_query(state)

        full_response = ""
        async for chunk in service.chat_stream(enhanced_query, db=db_session, history_messages=history_messages):
            if not isinstance(chunk, dict):
                full_response += str(chunk)
                yield {"final_response": full_response}
                continue

            chunk_type = chunk.get("type", "")

            if chunk_type == "content":
                content = chunk.get("content", "")
                full_response += content
                yield {"final_response": full_response}

            elif chunk_type == "skill_dependency_confirm":
                bus = get_side_channel()
                if bus:
                    logger.info(f"[MainStreamNode] 技能依赖确认事件 → SideChannel: {chunk.get('skill_name')}")
                    bus.push(chunk)
                else:
                    logger.warning("[MainStreamNode] SideChannel 未初始化，skill_dependency_confirm 事件丢失")
                # 立即 yield 一次状态更新，触发 LangGraphService 的 SideChannel pop
                yield {"final_response": full_response}

            elif chunk_type in ("tool_call", "tool_result"):
                logger.debug(f"[MainStreamNode] {chunk_type}: {chunk.get('name', '')}")

            elif chunk_type in ("done", "interrupted", "error"):
                logger.info(f"[MainStreamNode] 流结束: {chunk_type}")

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

        logger.info(f"[MainStreamNode] Stream completed (duration={duration_ms:.1f}ms, len={len(full_response)})")

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"[MainStreamNode] Error: {e}", exc_info=True)

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

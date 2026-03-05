"""
RAG 检索节点

使用 RagService 进行知识库检索，提供 LangGraph 兼容的节点函数
支持共享记忆系统（通过 ContextVar 传递）
"""
import time
import logging
from typing import Dict, Any

from app.langchain.graph.state import SupervisorState, StateAdapter, get_db_session, get_shared_memory
from app.langchain.graph.adapters.rag_adapter import RagAdapter
from app.langchain.llm import get_llm

logger = logging.getLogger(__name__)


async def rag_retrieve_node(state: SupervisorState) -> Dict[str, Any]:
    """
    RAG 检索节点
    
    从知识库检索相关内容
    
    Args:
        state: 当前状态
        
    Returns:
        更新后的状态片段
    """
    start_time = time.time()
    query = state.get("query", "")
    kb_hints = state.get("kb_hints", [])
    user_id = state.get("user_id")
    db_session = get_db_session()
    shared_memory = get_shared_memory()
    
    logger.info(f"[RagNode] Retrieving for query: {query[:50]}...")
    logger.info(f"[RagNode] KB hints: {kb_hints}")
    logger.info(f"[RagNode] Has shared_memory: {shared_memory is not None}")
    
    try:
        from app.langchain.services.rag import RagService, RagServiceConfig
        
        config = RagServiceConfig(
            max_history_turns=5,
            max_context_tokens=4000,
            top_k=5,
            use_hybrid=True,
            use_rerank=True,
        )
        
        rag_service = RagService(
            user_id=user_id,
            db_session=db_session,
            config=config,
            short_term_memory=shared_memory,
        )
        
        result = await rag_service.process_query(
            query=query,
            kb_ids=kb_hints if kb_hints else None,
        )
        
        update = RagAdapter.to_state(result, dict(state))
        
        duration_ms = (time.time() - start_time) * 1000
        
        state = StateAdapter.record_node_execution(
            state,
            node_name="rag_retrieve",
            success=True,
            duration_ms=duration_ms,
        )
        update["node_executions"] = state.get("node_executions", [])
        
        logger.info(f"[RagNode] Retrieved {len(result.documents) if hasattr(result, 'documents') else 0} docs (duration={duration_ms:.1f}ms)")
        
        return update
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"[RagNode] Error: {e}")
        
        state = StateAdapter.record_node_execution(
            state,
            node_name="rag_retrieve",
            success=False,
            duration_ms=duration_ms,
            error=str(e),
        )
        
        return {
            "rag_context": "",
            "rag_sources": [],
            "error": str(e),
            "error_node": "rag_retrieve",
            "node_executions": state.get("node_executions", []),
        }


async def rag_chat_node(state: SupervisorState) -> Dict[str, Any]:
    """
    RAG 对话节点
    
    使用 RAG 进行对话式问答
    
    Args:
        state: 当前状态
        
    Returns:
        更新后的状态片段
    """
    start_time = time.time()
    query = state.get("query", "")
    kb_hints = state.get("kb_hints", [])
    user_id = state.get("user_id")
    db_session = get_db_session()
    shared_memory = get_shared_memory()
    
    logger.info(f"[RagChatNode] Chat for query: {query[:50]}...")
    logger.info(f"[RagChatNode] Has shared_memory: {shared_memory is not None}")
    
    try:
        from app.langchain.services.rag import RagService, RagServiceConfig
        
        config = RagServiceConfig(
            max_history_turns=10,
            max_context_tokens=4000,
            top_k=5,
        )
        
        rag_service = RagService(
            user_id=user_id,
            db_session=db_session,
            config=config,
            short_term_memory=shared_memory,
        )
        
        result = await rag_service.process_query(
            query=query,
            kb_ids=kb_hints if kb_hints else None,
            top_k=5,
        )
        
        update = {
            "rag_context": result.formatted_context,
            "rag_sources": [
                {
                    "id": str(s.chunk_id) if hasattr(s, 'chunk_id') else "",
                    "title": s.doc_name if hasattr(s, 'doc_name') else "",
                    "score": s.score if hasattr(s, 'score') else 0,
                }
                for s in result.documents
            ],
            "rewritten_query": result.rewritten_query,
        }
        
        duration_ms = (time.time() - start_time) * 1000
        
        state = StateAdapter.record_node_execution(
            state,
            node_name="rag_chat",
            success=True,
            duration_ms=duration_ms,
        )
        update["node_executions"] = state.get("node_executions", [])
        
        logger.info(f"[RagChatNode] Chat completed (duration={duration_ms:.1f}ms)")
        
        return update
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"[RagChatNode] Error: {e}")
        
        state = StateAdapter.record_node_execution(
            state,
            node_name="rag_chat",
            success=False,
            duration_ms=duration_ms,
            error=str(e),
        )
        
        return {
            "rag_context": "",
            "error": str(e),
            "error_node": "rag_chat",
            "node_executions": state.get("node_executions", []),
        }

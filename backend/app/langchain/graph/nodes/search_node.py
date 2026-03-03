"""
互联网搜索节点

包装现有 ResearcherAgent，提供 LangGraph 兼容的节点函数
"""
import time
import logging
from typing import Dict, Any

from app.langchain.graph.state import SupervisorState, StateAdapter
from app.langchain.graph.adapters.search_adapter import SearchAdapter
from app.langchain.llm import get_llm

logger = logging.getLogger(__name__)


async def web_search_node(state: SupervisorState) -> Dict[str, Any]:
    """
    互联网搜索节点
    
    使用搜索引擎搜索互联网内容
    
    Args:
        state: 当前状态
        
    Returns:
        更新后的状态片段
    """
    start_time = time.time()
    query = state.get("query", "")
    
    logger.info(f"[SearchNode] Searching for: {query[:50]}...")
    
    try:
        from app.langchain.agents.researcher_agent import ResearcherAgent
        from app.config import settings
        
        llm = get_llm()
        
        researcher = ResearcherAgent(llm=llm)
        
        max_iterations = getattr(settings, 'RESEARCHER_MAX_ITERATIONS', 3)
        
        result = await researcher.research(
            topic=query,
            max_iterations=max_iterations,
        )
        
        update = SearchAdapter.to_state(result, dict(state))
        
        duration_ms = (time.time() - start_time) * 1000
        
        state = StateAdapter.record_node_execution(
            state,
            node_name="web_search",
            success=True,
            duration_ms=duration_ms,
        )
        update["node_executions"] = state.get("node_executions", [])
        
        logger.info(f"[SearchNode] Search completed (duration={duration_ms:.1f}ms)")
        
        return update
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"[SearchNode] Error: {e}")
        
        state = StateAdapter.record_node_execution(
            state,
            node_name="web_search",
            success=False,
            duration_ms=duration_ms,
            error=str(e),
        )
        
        return {
            "search_context": "",
            "search_sources": [],
            "error": str(e),
            "error_node": "web_search",
            "node_executions": state.get("node_executions", []),
        }


async def parallel_search_node(state: SupervisorState) -> Dict[str, Any]:
    """
    并行搜索节点
    
    同时执行 RAG 和 Web 搜索，用于低置信度场景
    
    Args:
        state: 当前状态
        
    Returns:
        更新后的状态片段
    """
    import asyncio
    
    start_time = time.time()
    query = state.get("query", "")
    
    logger.info(f"[ParallelNode] Parallel search for: {query[:50]}...")
    
    try:
        from app.langchain.agents.rag_agent import RagAgent
        from app.langchain.agents.researcher_agent import ResearcherAgent
        from app.config import settings
        
        llm = get_llm()
        user_id = state.get("user_id")
        db_session = state.get("db_session")
        kb_hints = state.get("kb_hints", [])
        
        rag_agent = RagAgent(
            llm=llm,
            user_id=user_id,
            db_session=db_session,
        )
        
        researcher = ResearcherAgent(llm=llm)
        
        rag_task = rag_agent.process_query_with_context(
            query=query,
            kb_ids=kb_hints if kb_hints else None,
        )
        
        search_task = researcher.research(
            topic=query,
            max_iterations=getattr(settings, 'RESEARCHER_MAX_ITERATIONS', 3),
        )
        
        results = await asyncio.gather(
            rag_task, search_task,
            return_exceptions=True
        )
        
        update = dict(state)
        
        if not isinstance(results[0], Exception):
            from app.langchain.graph.adapters.rag_adapter import RagAdapter
            update = RagAdapter.to_state(results[0], update)
        else:
            logger.warning(f"[ParallelNode] RAG failed: {results[0]}")
            update["rag_context"] = ""
        
        if not isinstance(results[1], Exception):
            update = SearchAdapter.to_state(results[1], update)
        else:
            logger.warning(f"[ParallelNode] Search failed: {results[1]}")
            update["search_context"] = ""
        
        duration_ms = (time.time() - start_time) * 1000
        
        state = StateAdapter.record_node_execution(
            state,
            node_name="parallel_search",
            success=True,
            duration_ms=duration_ms,
        )
        update["node_executions"] = state.get("node_executions", [])
        
        logger.info(f"[ParallelNode] Parallel search completed (duration={duration_ms:.1f}ms)")
        
        return update
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"[ParallelNode] Error: {e}")
        
        state = StateAdapter.record_node_execution(
            state,
            node_name="parallel_search",
            success=False,
            duration_ms=duration_ms,
            error=str(e),
        )
        
        return {
            "rag_context": "",
            "search_context": "",
            "error": str(e),
            "error_node": "parallel_search",
            "node_executions": state.get("node_executions", []),
        }


def merge_parallel_results(state: SupervisorState) -> Dict[str, Any]:
    """
    合并并行搜索结果
    
    Args:
        state: 当前状态
        
    Returns:
        合并后的上下文
    """
    from app.langchain.graph.adapters.search_adapter import ParallelResultAdapter
    
    merged_context = ParallelResultAdapter.format_combined_context(state)
    
    return {
        "merged_context": merged_context,
    }

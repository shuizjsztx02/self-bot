"""
意图分类节点

包装现有 IntentClassifier，提供 LangGraph 兼容的节点函数
"""
import time
import logging
from typing import Dict, Any

from app.langchain.graph.state import SupervisorState, StateAdapter, QueryIntent
from app.langchain.graph.adapters.intent_adapter import IntentAdapter
from app.langchain.llm import get_llm

logger = logging.getLogger(__name__)


async def classify_intent_node(state: SupervisorState) -> Dict[str, Any]:
    """
    意图分类节点
    
    分析用户查询意图，返回分类结果
    
    Args:
        state: 当前状态
        
    Returns:
        更新后的状态片段
    """
    start_time = time.time()
    query = state.get("query", "")
    
    logger.info(f"[IntentNode] Classifying query: {query[:50]}...")
    
    try:
        from app.langchain.services.supervisor.intent_classifier import (
            IntentClassifier,
            IntentResult,
        )
        
        llm = get_llm()
        db_session = state.get("db_session")
        
        classifier = IntentClassifier(llm=llm, db_session=db_session)
        
        result = await classifier.classify_with_alternatives(query)
        
        intent_value = result.intent.value if result.intent else "general_chat"
        
        update = {
            "intent": intent_value,
            "confidence": result.confidence,
            "kb_hints": result.kb_hints,
            "secondary_intents": result.secondary_intents,
            "reasoning": result.reasoning,
        }
        
        duration_ms = (time.time() - start_time) * 1000
        
        state = StateAdapter.record_node_execution(
            state,
            node_name="classify_intent",
            success=True,
            duration_ms=duration_ms,
        )
        update["node_executions"] = state.get("node_executions", [])
        
        logger.info(f"[IntentNode] Result: {intent_value} (confidence={result.confidence:.2f}, duration={duration_ms:.1f}ms)")
        
        return update
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"[IntentNode] Error: {e}")
        
        state = StateAdapter.record_node_execution(
            state,
            node_name="classify_intent",
            success=False,
            duration_ms=duration_ms,
            error=str(e),
        )
        
        return {
            "intent": "general_chat",
            "confidence": 0.0,
            "kb_hints": [],
            "error": str(e),
            "error_node": "classify_intent",
            "node_executions": state.get("node_executions", []),
        }


def determine_route(state: SupervisorState) -> str:
    """
    根据意图确定路由
    
    Args:
        state: 当前状态
        
    Returns:
        路由名称
    """
    intent = state.get("intent", "general_chat")
    confidence = state.get("confidence", 0.0)
    
    if confidence < 0.65:
        logger.info(f"[Router] Low confidence ({confidence:.2f}), routing to parallel")
        return "parallel"
    
    route_map = {
        "kb_query": "rag",
        "search_task": "search",
        "document_task": "direct",
        "data_analysis": "direct",
        "code_task": "direct",
        "tool_task": "direct",
        "general_chat": "direct",
        "ambiguous": "parallel",
    }
    
    route = route_map.get(intent, "direct")
    logger.info(f"[Router] Intent={intent}, Route={route}")
    
    return route

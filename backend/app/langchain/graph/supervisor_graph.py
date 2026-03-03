"""
Supervisor 图构建器

构建完整的 LangGraph 工作流图
"""
import logging
from typing import Dict, Any, Optional

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from app.langchain.graph.state import SupervisorState, create_initial_state
from app.langchain.graph.nodes import (
    classify_intent_node,
    determine_route,
    rag_retrieve_node,
    web_search_node,
    parallel_search_node,
    generate_response_node,
    finalize_node,
)

logger = logging.getLogger(__name__)


def route_by_intent(state: SupervisorState) -> str:
    """
    根据意图路由
    
    这是条件边的路由函数
    
    Args:
        state: 当前状态
        
    Returns:
        下一个节点名称
    """
    return determine_route(state)


def build_base_graph() -> StateGraph:
    """
    构建基础图结构
    
    包含线性流程：意图分类 -> 响应生成
    
    Returns:
        编译后的 StateGraph
    """
    graph = StateGraph(SupervisorState)
    
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("generate_response", generate_response_node)
    graph.add_node("finalize", finalize_node)
    
    graph.set_entry_point("classify_intent")
    graph.add_edge("classify_intent", "generate_response")
    graph.add_edge("generate_response", "finalize")
    graph.add_edge("finalize", END)
    
    return graph.compile()


def build_supervisor_graph() -> StateGraph:
    """
    构建完整的 Supervisor 图
    
    包含条件路由和并行执行
    
    Returns:
        编译后的 StateGraph
    """
    graph = StateGraph(SupervisorState)
    
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("rag_retrieve", rag_retrieve_node)
    graph.add_node("web_search", web_search_node)
    graph.add_node("parallel_search", parallel_search_node)
    graph.add_node("generate_response", generate_response_node)
    graph.add_node("finalize", finalize_node)
    
    graph.set_entry_point("classify_intent")
    
    graph.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "rag": "rag_retrieve",
            "search": "web_search",
            "parallel": "parallel_search",
            "direct": "generate_response",
        }
    )
    
    graph.add_edge("rag_retrieve", "generate_response")
    graph.add_edge("web_search", "generate_response")
    graph.add_edge("parallel_search", "generate_response")
    graph.add_edge("generate_response", "finalize")
    graph.add_edge("finalize", END)
    
    return graph.compile()


def build_simple_graph() -> StateGraph:
    """
    构建简单图结构
    
    仅包含意图分类和响应生成，用于测试
    
    Returns:
        编译后的简单图
    """
    graph = StateGraph(SupervisorState)
    
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("generate_response", generate_response_node)
    
    graph.set_entry_point("classify_intent")
    graph.add_edge("classify_intent", "generate_response")
    graph.add_edge("generate_response", END)
    
    return graph.compile()


class SupervisorGraphRunner:
    """
    Supervisor 图运行器
    
    提供便捷的图执行接口
    """
    
    def __init__(self, use_full_graph: bool = True):
        """
        初始化运行器
        
        Args:
            use_full_graph: 是否使用完整图（包含条件路由）
        """
        if use_full_graph:
            self._graph = build_supervisor_graph()
        else:
            self._graph = build_simple_graph()
    
    async def run(
        self,
        query: str,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        db_session: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        运行图
        
        Args:
            query: 用户查询
            user_id: 用户 ID
            conversation_id: 会话 ID
            db_session: 数据库会话
            
        Returns:
            最终状态
        """
        initial_state = create_initial_state(
            query=query,
            user_id=user_id,
            conversation_id=conversation_id,
            db_session=db_session,
        )
        
        logger.info(f"[GraphRunner] Starting graph execution for query: {query[:50]}...")
        
        result = await self._graph.ainvoke(initial_state)
        
        logger.info(f"[GraphRunner] Graph execution completed")
        
        return result
    
    async def stream(
        self,
        query: str,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        db_session: Optional[Any] = None,
    ):
        """
        流式运行图
        
        Args:
            query: 用户查询
            user_id: 用户 ID
            conversation_id: 会话 ID
            db_session: 数据库会话
            
        Yields:
            状态更新
        """
        initial_state = create_initial_state(
            query=query,
            user_id=user_id,
            conversation_id=conversation_id,
            db_session=db_session,
        )
        
        logger.info(f"[GraphRunner] Starting stream execution for query: {query[:50]}...")
        
        async for event in self._graph.astream(initial_state):
            yield event
    
    def get_graph_structure(self) -> str:
        """
        获取图结构描述
        
        Returns:
            图结构的字符串表示
        """
        try:
            return self._graph.get_graph().draw_mermaid()
        except Exception:
            return "Graph structure not available"

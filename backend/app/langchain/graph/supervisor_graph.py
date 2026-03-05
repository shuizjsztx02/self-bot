"""
Supervisor 图构建器

构建完整的 LangGraph 工作流图，支持 Checkpointer 状态持久化
"""
import logging
from typing import Dict, Any, Optional

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

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


def build_base_graph(checkpointer: Optional[AsyncSqliteSaver] = None) -> StateGraph:
    """
    构建基础图结构
    
    包含线性流程：意图分类 -> 响应生成
    
    Args:
        checkpointer: 可选的 checkpointer 实例
        
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
    
    return graph.compile(checkpointer=checkpointer)


def build_supervisor_graph(checkpointer: Optional[AsyncSqliteSaver] = None) -> StateGraph:
    """
    构建完整的 Supervisor 图
    
    包含条件路由和并行执行
    
    Args:
        checkpointer: 可选的 checkpointer 实例，用于状态持久化
        
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
    
    compiled_graph = graph.compile(checkpointer=checkpointer)
    
    if checkpointer:
        logger.info("[GraphBuilder] Graph compiled with checkpointer enabled")
    else:
        logger.info("[GraphBuilder] Graph compiled without checkpointer")
    
    return compiled_graph


def build_simple_graph(checkpointer: Optional[AsyncSqliteSaver] = None) -> StateGraph:
    """
    构建简单图结构
    
    仅包含意图分类和响应生成，用于测试
    
    Args:
        checkpointer: 可选的 checkpointer 实例
        
    Returns:
        编译后的简单图
    """
    graph = StateGraph(SupervisorState)
    
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("generate_response", generate_response_node)
    
    graph.set_entry_point("classify_intent")
    graph.add_edge("classify_intent", "generate_response")
    graph.add_edge("generate_response", END)
    
    return graph.compile(checkpointer=checkpointer)


class SupervisorGraphRunner:
    """
    Supervisor 图运行器
    
    提供便捷的图执行接口，支持:
    1. 同步/异步执行
    2. 流式输出
    3. Checkpointer 状态持久化
    4. 状态恢复与查询
    """
    
    def __init__(
        self, 
        use_full_graph: bool = True,
        use_checkpointer: bool = True,
    ):
        """
        初始化运行器
        
        Args:
            use_full_graph: 是否使用完整图（包含条件路由）
            use_checkpointer: 是否启用 checkpointer
        """
        self._use_full_graph = use_full_graph
        self._use_checkpointer = use_checkpointer
        self._graph = None
        self._checkpointer: Optional[AsyncSqliteSaver] = None
        self._initialized = False
    
    async def _ensure_initialized(self):
        """确保图已初始化（异步）"""
        if self._initialized:
            return
        
        if self._use_checkpointer:
            from app.langchain.graph.checkpointer import get_checkpointer_manager
            manager = get_checkpointer_manager()
            self._checkpointer = await manager.get_saver()
            
            if self._checkpointer is None:
                logger.warning("[GraphRunner] Checkpointer requested but not available, running without persistence")
        
        if self._use_full_graph:
            self._graph = build_supervisor_graph(self._checkpointer)
        else:
            self._graph = build_simple_graph(self._checkpointer)
        
        self._initialized = True
        logger.info(f"[GraphRunner] Initialized: full_graph={self._use_full_graph}, checkpointer={self._checkpointer is not None}")
    
    def _build_config(
        self,
        thread_id: Optional[str] = None,
        checkpoint_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        构建执行配置
        
        Args:
            thread_id: 线程 ID (用于状态隔离和恢复)
            checkpoint_id: 检查点 ID (用于从特定检查点恢复)
            
        Returns:
            配置字典
        """
        config = {
            "configurable": {}
        }
        
        if thread_id:
            config["configurable"]["thread_id"] = thread_id
        
        if checkpoint_id:
            config["configurable"]["checkpoint_id"] = checkpoint_id
        
        return config
    
    async def run(
        self,
        query: str,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        db_session: Optional[Any] = None,
        thread_id: Optional[str] = None,
        checkpoint_id: Optional[str] = None,
        history_messages: Optional[list] = None,
        shared_memory: Optional[Any] = None,
        long_term_memory: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        运行图
        
        Args:
            query: 用户查询
            user_id: 用户 ID
            conversation_id: 会话 ID
            db_session: 数据库会话
            thread_id: 线程 ID (用于状态持久化，默认使用 conversation_id)
            checkpoint_id: 检查点 ID (用于从特定检查点恢复)
            history_messages: 历史消息列表 (用于上下文)
            shared_memory: 短期记忆实例 (共享)
            long_term_memory: 长期记忆实例 (共享)
            
        Returns:
            最终状态
        """
        await self._ensure_initialized()
        
        effective_thread_id = thread_id or conversation_id
        
        config = self._build_config(effective_thread_id, checkpoint_id)
        
        initial_state = create_initial_state(
            query=query,
            user_id=user_id,
            conversation_id=conversation_id,
            db_session=db_session,
            history_messages=history_messages,
            shared_memory=shared_memory,
            long_term_memory=long_term_memory,
        )
        
        logger.info(f"[GraphRunner] Starting graph execution: query={query[:50]}..., thread_id={effective_thread_id}, history_count={len(history_messages) if history_messages else 0}, has_shared_memory={shared_memory is not None}")
        
        result = await self._graph.ainvoke(initial_state, config=config)
        
        logger.info(f"[GraphRunner] Graph execution completed")
        
        return result
    
    async def stream(
        self,
        query: str,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        db_session: Optional[Any] = None,
        thread_id: Optional[str] = None,
        checkpoint_id: Optional[str] = None,
        history_messages: Optional[list] = None,
        shared_memory: Optional[Any] = None,
        long_term_memory: Optional[Any] = None,
    ):
        """
        流式运行图
        
        Args:
            query: 用户查询
            user_id: 用户 ID
            conversation_id: 会话 ID
            db_session: 数据库会话
            thread_id: 线程 ID (用于状态持久化)
            checkpoint_id: 检查点 ID (用于从特定检查点恢复)
            history_messages: 历史消息列表 (用于上下文)
            shared_memory: 短期记忆实例 (共享)
            long_term_memory: 长期记忆实例 (共享)
            
        Yields:
            状态更新事件
        """
        await self._ensure_initialized()
        
        effective_thread_id = thread_id or conversation_id
        
        config = self._build_config(effective_thread_id, checkpoint_id)
        
        initial_state = create_initial_state(
            query=query,
            user_id=user_id,
            conversation_id=conversation_id,
            db_session=db_session,
            history_messages=history_messages,
            shared_memory=shared_memory,
            long_term_memory=long_term_memory,
        )
        
        logger.info(f"[GraphRunner] Starting stream execution: query={query[:50]}..., thread_id={effective_thread_id}, history_count={len(history_messages) if history_messages else 0}, has_shared_memory={shared_memory is not None}")
        
        async for event in self._graph.astream(initial_state, config=config):
            yield event
    
    async def get_state(
        self,
        thread_id: str,
        checkpoint_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        获取指定线程的状态
        
        Args:
            thread_id: 线程 ID
            checkpoint_id: 检查点 ID (可选)
            
        Returns:
            状态字典或 None
        """
        await self._ensure_initialized()
        
        if not self._checkpointer:
            logger.warning("[GraphRunner] Checkpointer not enabled, cannot get state")
            return None
        
        config = self._build_config(thread_id, checkpoint_id)
        
        try:
            state_snapshot = await self._graph.aget_state(config)
            
            if state_snapshot:
                return {
                    "values": state_snapshot.values,
                    "next": state_snapshot.next,
                    "config": state_snapshot.config,
                    "metadata": state_snapshot.metadata,
                    "created_at": state_snapshot.created_at,
                    "parent_config": state_snapshot.parent_config,
                }
        except Exception as e:
            logger.error(f"[GraphRunner] Failed to get state: {e}")
        
        return None
    
    async def get_state_history(
        self,
        thread_id: str,
        limit: int = 10,
    ):
        """
        获取状态历史
        
        Args:
            thread_id: 线程 ID
            limit: 最大返回数量
            
        Yields:
            状态快照
        """
        await self._ensure_initialized()
        
        if not self._checkpointer:
            logger.warning("[GraphRunner] Checkpointer not enabled, cannot get state history")
            return
        
        config = self._build_config(thread_id)
        
        count = 0
        async for state_snapshot in self._graph.aget_state_history(config):
            if count >= limit:
                break
            
            yield {
                "values": state_snapshot.values,
                "next": state_snapshot.next,
                "config": state_snapshot.config,
                "metadata": state_snapshot.metadata,
                "created_at": state_snapshot.created_at,
                "parent_config": state_snapshot.parent_config,
            }
            count += 1
    
    async def update_state(
        self,
        thread_id: str,
        values: Dict[str, Any],
        checkpoint_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        更新状态
        
        Args:
            thread_id: 线程 ID
            values: 要更新的值
            checkpoint_id: 检查点 ID (可选)
            
        Returns:
            更新后的配置
        """
        await self._ensure_initialized()
        
        if not self._checkpointer:
            logger.warning("[GraphRunner] Checkpointer not enabled, cannot update state")
            return None
        
        config = self._build_config(thread_id, checkpoint_id)
        
        try:
            result = await self._graph.aupdate_state(config, values)
            logger.info(f"[GraphRunner] State updated for thread_id={thread_id}")
            return result
        except Exception as e:
            logger.error(f"[GraphRunner] Failed to update state: {e}")
            return None
    
    def get_graph_structure(self) -> str:
        """
        获取图结构描述
        
        Returns:
            图结构的 Mermaid 字符串表示
        """
        if self._graph is None:
            return "Graph not initialized"
        
        try:
            return self._graph.get_graph().draw_mermaid()
        except Exception:
            return "Graph structure not available"
    
    @property
    def has_checkpointer(self) -> bool:
        """是否启用了 checkpointer"""
        return self._checkpointer is not None

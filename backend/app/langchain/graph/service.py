"""
LangGraph 服务层

提供与现有 API 兼容的接口，内部使用 LangGraph 架构
支持 Checkpointer 状态持久化
支持对话历史加载和会话隔离
支持共享记忆系统
"""
import logging
from typing import Dict, Any, Optional, AsyncIterator, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from pathlib import Path

from app.langchain.graph import SupervisorGraphRunner
from app.langchain.graph.state import create_initial_state
from app.config import settings

logger = logging.getLogger(__name__)


class LangGraphService:
    """
    LangGraph 服务
    
    提供与现有 Agent 接口兼容的方法，内部使用 LangGraph 图
    
    功能:
    1. 同步/异步对话
    2. 流式输出
    3. 状态持久化 (通过 Checkpointer)
    4. 状态查询与恢复
    5. 对话历史加载 (从数据库)
    6. 会话隔离 (通过 conversation_id)
    7. 共享记忆系统 (短期/长期记忆)
    """
    
    def __init__(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        db_session: Optional[AsyncSession] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        use_checkpointer: bool = True,
    ):
        """
        初始化服务
        
        Args:
            conversation_id: 会话 ID
            user_id: 用户 ID
            db_session: 数据库会话
            provider: LLM 提供商
            model: 模型名称
            use_checkpointer: 是否启用 checkpointer
        """
        self.conversation_id = conversation_id
        self.user_id = user_id
        self.db_session = db_session
        self.provider = provider
        self.model = model
        self._runner = SupervisorGraphRunner(
            use_full_graph=True,
            use_checkpointer=use_checkpointer,
        )
        self.conversation_memory: List[BaseMessage] = []
        
        from app.langchain.memory import ShortTermMemory, LongTermMemory, MemorySummarizer
        
        self.shared_memory = ShortTermMemory(
            max_tokens=settings.MEMORY_MAX_TOKENS,
            summary_threshold=settings.MEMORY_SUMMARY_THRESHOLD,
            keep_recent_messages=settings.MEMORY_KEEP_RECENT,
            on_summary_needed=self._generate_summary,
            on_store_summary=self._store_summary_to_long_term,
        )
        
        self.long_term_memory = LongTermMemory(
            storage_path=settings.AGENT_MEMORY_PATH,
            chroma_path=settings.AGENT_VECTOR_PATH,
            embedding_model=settings.EMBEDDING_MODEL,
            reranker_model=settings.RERANKER_MODEL,
        )
        
        self.summarizer = MemorySummarizer(provider=provider, model=model)
    
    async def _generate_summary(self, messages: List) -> str:
        """生成对话摘要"""
        return await self.summarizer.summarize(messages)
    
    async def _store_summary_to_long_term(self, summary_content: str, message_count: int):
        """将摘要存储到长期记忆"""
        try:
            await self.long_term_memory.store(
                content=summary_content,
                importance=4,
                category="summary",
                tags=["auto_summary", f"messages_{message_count}"],
                source_conversation_id=self.conversation_id,
            )
            logger.info(f"[LangGraphService] Summary synced to long-term memory: {message_count} messages")
        except Exception as e:
            logger.warning(f"[LangGraphService] Failed to sync summary to long-term memory: {e}")
    
    async def load_history(
        self,
        db_session: Optional[AsyncSession] = None,
        limit: int = 20,
    ) -> int:
        """
        从数据库加载对话历史到共享记忆
        
        Args:
            db_session: 数据库会话
            limit: 加载的消息数量限制
            
        Returns:
            加载的消息数量
        """
        db = db_session or self.db_session
        if not db:
            logger.warning("[LangGraphService] No db_session available for loading history")
            return 0
        
        if not self.conversation_id:
            logger.warning("[LangGraphService] No conversation_id available for loading history")
            return 0
        
        try:
            from app.langchain.models.database import Message
            
            result = await db.execute(
                select(Message)
                .where(Message.conversation_id == self.conversation_id)
                .order_by(Message.created_at.desc())
                .limit(limit)
            )
            messages = result.scalars().all()
            messages = list(reversed(messages))
            
            self.conversation_memory = []
            
            for msg in messages:
                if msg.role == "user":
                    self.shared_memory.add_short_term_memory(HumanMessage(content=msg.content))
                    self.conversation_memory.append(HumanMessage(content=msg.content))
                elif msg.role == "assistant":
                    self.shared_memory.add_short_term_memory(AIMessage(content=msg.content))
                    self.conversation_memory.append(AIMessage(content=msg.content))
                elif msg.role == "system":
                    self.shared_memory.add_short_term_memory(SystemMessage(content=msg.content))
                    self.conversation_memory.append(SystemMessage(content=msg.content))
            
            logger.info(f"[LangGraphService] Loaded {len(self.conversation_memory)} history messages for conversation {self.conversation_id}")
            return len(self.conversation_memory)
            
        except Exception as e:
            logger.error(f"[LangGraphService] Failed to load history: {e}")
            return 0
    
    def get_history_messages(self) -> List[BaseMessage]:
        """获取历史消息列表"""
        return self.conversation_memory.copy()
    
    def clear_memory(self):
        """清空对话内存"""
        self.conversation_memory = []
        self.shared_memory.clear()
        logger.info(f"[LangGraphService] Cleared conversation memory for {self.conversation_id}")
    
    def add_message_to_memory(self, message: BaseMessage):
        """添加消息到内存"""
        self.conversation_memory.append(message)
        self.shared_memory.add_short_term_memory(message)
    
    async def chat(
        self, 
        message: str, 
        db: Optional[AsyncSession] = None,
        thread_id: Optional[str] = None,
        checkpoint_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        同步聊天接口
        
        Args:
            message: 用户消息
            db: 数据库会话
            thread_id: 线程 ID (用于状态持久化，默认使用 conversation_id)
            checkpoint_id: 检查点 ID (用于从特定检查点恢复)
            
        Returns:
            包含 output 和 tool_calls 的字典
        """
        db = db or self.db_session
        effective_thread_id = thread_id or self.conversation_id
        
        logger.info(f"[LangGraphService] Processing chat: {message[:50]}..., thread_id={effective_thread_id}")
        
        # 🆕 自进化系统集成：开始追踪
        from app.langchain.tracing.execution import ExecutionTracer
        tracer = ExecutionTracer()
        trace = tracer.start_trace(
            conversation_id=self.conversation_id or "",
            query=message,
        )
        
        try:
            from app.langchain.graph.state import set_shared_memory, set_long_term_memory
            
            set_shared_memory(self.shared_memory)
            set_long_term_memory(self.long_term_memory)
            
            history_messages = self.conversation_memory.copy()
            
            result = await self._runner.run(
                query=message,
                user_id=self.user_id,
                conversation_id=self.conversation_id,
                db_session=db,
                thread_id=effective_thread_id,
                checkpoint_id=checkpoint_id,
                history_messages=history_messages,
                shared_memory=self.shared_memory,
                long_term_memory=self.long_term_memory,
            )
            
            output = result.get("final_response", "")
            tool_calls = result.get("tool_calls", [])
            
            if result.get("error"):
                logger.warning(f"[LangGraphService] Graph error: {result.get('error')}")
                if not output:
                    output = f"处理请求时发生错误: {result.get('error')}"
            
            self.conversation_memory.append(HumanMessage(content=message))
            self.shared_memory.add_short_term_memory(HumanMessage(content=message))
            if output:
                self.conversation_memory.append(AIMessage(content=output))
                self.shared_memory.add_short_term_memory(AIMessage(content=output))
            
            # 🆕 自进化系统集成：记录关键信息
            trace.intent_classification = result.get("intent", {}).get("type") if isinstance(result.get("intent"), dict) else result.get("intent")
            trace.intent_confidence = result.get("confidence", 0.0)
            trace.routed_nodes = result.get("node_executions", [])
            trace.skills_activated = result.get("skills_activated", [])
            trace.response = output
            
            # 结束并保存轨迹
            tracer.end_trace(
                trace_id=trace.trace_id,
                response=output,
                token_usage=result.get("token_usage", {}),
            )
            await tracer.save_trace(trace.trace_id)
            
            return {
                "output": output,
                "tool_calls": tool_calls,
                "intent": result.get("intent"),
                "confidence": result.get("confidence"),
                "node_executions": result.get("node_executions", []),
                "thread_id": effective_thread_id,
            }
            
        except Exception as e:
            logger.error(f"[LangGraphService] Chat error: {e}")
            
            # 🆕 自进化系统集成：记录错误
            tracer.end_trace(trace_id=trace.trace_id, error=str(e))
            await tracer.save_trace(trace.trace_id)
            
            return {
                "output": f"抱歉，处理请求时发生错误: {str(e)}",
                "tool_calls": [],
                "error": str(e),
            }
    
    async def chat_stream(
        self,
        message: str,
        db: Optional[AsyncSession] = None,
        thread_id: Optional[str] = None,
        checkpoint_id: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        流式聊天接口
        
        Args:
            message: 用户消息
            db: 数据库会话
            thread_id: 线程 ID (用于状态持久化)
            checkpoint_id: 检查点 ID (用于从特定检查点恢复)
            
        Yields:
            SSE 格式的响应片段
        """
        from datetime import datetime, timezone
        
        db = db or self.db_session
        effective_thread_id = thread_id or self.conversation_id
        
        logger.info(f"[LangGraphService] Processing stream chat: {message[:50]}..., thread_id={effective_thread_id}")
        
        full_response = ""
        
        try:
            from app.langchain.graph.state import set_shared_memory, set_long_term_memory
            
            set_shared_memory(self.shared_memory)
            set_long_term_memory(self.long_term_memory)
            
            history_messages = self.conversation_memory.copy()
            
            async for event in self._runner.stream(
                query=message,
                user_id=self.user_id,
                conversation_id=self.conversation_id,
                db_session=db,
                thread_id=effective_thread_id,
                checkpoint_id=checkpoint_id,
                history_messages=history_messages,
                shared_memory=self.shared_memory,
                long_term_memory=self.long_term_memory,
            ):
                for node_name, node_output in event.items():
                    if isinstance(node_output, dict):
                        if "final_response" in node_output and node_output["final_response"]:
                            content = node_output["final_response"]
                            full_response = content
                            data = {
                                "type": "content",
                                "content": content,
                                "node": node_name,
                            }
                            yield data
                        
                        if "stream_chunk" in node_output:
                            chunk = node_output["stream_chunk"]
                            full_response += chunk
                            data = {
                                "type": "chunk",
                                "content": chunk,
                                "node": node_name,
                            }
                            yield data
            
            self.conversation_memory.append(HumanMessage(content=message))
            self.shared_memory.add_short_term_memory(HumanMessage(content=message))
            if full_response:
                self.conversation_memory.append(AIMessage(content=full_response))
                self.shared_memory.add_short_term_memory(AIMessage(content=full_response))
            
            data = {
                "type": "done",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "thread_id": effective_thread_id,
            }
            yield data
            
        except Exception as e:
            logger.error(f"[LangGraphService] Stream error: {e}")
            data = {
                "type": "error",
                "error": str(e),
            }
            yield data
    
    async def get_conversation_state(
        self,
        thread_id: Optional[str] = None,
        checkpoint_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        获取会话状态
        
        Args:
            thread_id: 线程 ID (默认使用 conversation_id)
            checkpoint_id: 检查点 ID (可选)
            
        Returns:
            状态字典或 None
        """
        effective_thread_id = thread_id or self.conversation_id
        
        if not effective_thread_id:
            logger.warning("[LangGraphService] No thread_id available for state retrieval")
            return None
        
        return await self._runner.get_state(effective_thread_id, checkpoint_id)
    
    async def get_conversation_history(
        self,
        thread_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        获取会话历史状态
        
        Args:
            thread_id: 线程 ID (默认使用 conversation_id)
            limit: 最大返回数量
            
        Returns:
            状态历史列表
        """
        effective_thread_id = thread_id or self.conversation_id
        
        if not effective_thread_id:
            logger.warning("[LangGraphService] No thread_id available for history retrieval")
            return []
        
        history = []
        async for state in self._runner.get_state_history(effective_thread_id, limit):
            history.append(state)
        
        return history
    
    async def update_conversation_state(
        self,
        values: Dict[str, Any],
        thread_id: Optional[str] = None,
        checkpoint_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        更新会话状态
        
        Args:
            values: 要更新的值
            thread_id: 线程 ID (默认使用 conversation_id)
            checkpoint_id: 检查点 ID (可选)
            
        Returns:
            更新后的配置
        """
        effective_thread_id = thread_id or self.conversation_id
        
        if not effective_thread_id:
            logger.warning("[LangGraphService] No thread_id available for state update")
            return None
        
        return await self._runner.update_state(effective_thread_id, values, checkpoint_id)
    
    async def clear_conversation_state(
        self,
        thread_id: Optional[str] = None,
    ) -> bool:
        """
        清除会话状态
        
        Args:
            thread_id: 线程 ID (默认使用 conversation_id)
            
        Returns:
            是否成功清除
        """
        effective_thread_id = thread_id or self.conversation_id
        
        if not effective_thread_id:
            logger.warning("[LangGraphService] No thread_id available for state clearing")
            return False
        
        from app.langchain.graph.checkpointer import get_checkpointer_manager
        
        manager = get_checkpointer_manager()
        deleted_count = await manager.clear_thread(effective_thread_id)
        
        self.conversation_memory = []
        self.shared_memory.clear()
        
        logger.info(f"[LangGraphService] Cleared {deleted_count} checkpoints for thread_id={effective_thread_id}")
        return deleted_count > 0
    
    @property
    def has_checkpointer(self) -> bool:
        """是否启用了 checkpointer"""
        return self._runner.has_checkpointer
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """获取内存统计信息"""
        shared_stats = self.shared_memory.get_stats()
        
        from app.langchain.graph.checkpointer import get_checkpointer_manager
        manager = get_checkpointer_manager()
        checkpointer_stats = manager.get_stats()
        
        return {
            "conversation_id": self.conversation_id,
            "message_count": len(self.conversation_memory),
            "has_checkpointer": self.has_checkpointer,
            "shared_memory": {
                "token_count": shared_stats.get("token_count", 0),
                "max_tokens": shared_stats.get("max_tokens", 0),
                "utilization": shared_stats.get("utilization", "0%"),
                "summary_count": len(self.shared_memory.summaries),
            },
            "checkpointer": checkpointer_stats,
        }
    
    async def detect_incomplete_execution(
        self,
        thread_id: Optional[str] = None,
    ):
        """
        检测未完成的执行
        
        Args:
            thread_id: 线程 ID (默认使用 conversation_id)
            
        Returns:
            IncompleteExecution 或 None
        """
        effective_thread_id = thread_id or self.conversation_id
        
        if not effective_thread_id:
            return None
        
        from app.langchain.graph.checkpointer import get_checkpointer_manager
        
        manager = get_checkpointer_manager()
        return await manager.detect_incomplete_execution(effective_thread_id)
    
    async def get_checkpointer_metrics(self):
        """获取 Checkpointer 运行指标"""
        from app.langchain.graph.checkpointer import get_checkpointer_manager
        
        manager = get_checkpointer_manager()
        return manager.get_metrics()
    
    async def cleanup_expired_checkpoints(self) -> int:
        """清理过期的检查点"""
        from app.langchain.graph.checkpointer import get_checkpointer_manager
        
        manager = get_checkpointer_manager()
        return await manager.cleanup_expired()


async def get_agent(
    conversation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    db_session: Optional[AsyncSession] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    use_checkpointer: bool = True,
):
    """
    获取 Agent 实例
    
    注意: 推荐使用 agent_manager.get_agent() 以获得实例缓存和历史加载功能
    
    Args:
        conversation_id: 会话 ID
        user_id: 用户 ID
        db_session: 数据库会话
        provider: LLM 提供商
        model: 模型名称
        use_checkpointer: 是否启用 checkpointer
        
    Returns:
        LangGraphService 实例
    """
    logger.info("[AgentFactory] Creating LangGraphService (direct, no cache)")
    return LangGraphService(
        conversation_id=conversation_id,
        user_id=user_id,
        db_session=db_session,
        provider=provider,
        model=model,
        use_checkpointer=use_checkpointer,
    )

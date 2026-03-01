from typing import List, Optional, Callable, Awaitable
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from pydantic import BaseModel
from datetime import datetime, timezone
import asyncio
import uuid
import logging

from .token_counter import TokenCounter
from app.langchain.tracing.memory_trace import (
    start_memory_trace,
    end_memory_trace,
    memory_trace_step,
    get_memory_trace,
)

logger = logging.getLogger(__name__)


class MemoryConfig(BaseModel):
    max_tokens: int = 10000
    summary_threshold: float = 0.8
    keep_recent_messages: int = 10


class MemorySummary(BaseModel):
    id: str
    content: str
    token_count: int
    message_range: tuple[int, int]
    created_at: datetime
    importance: int = 3


class ShortTermMemory:
    def __init__(
        self,
        max_tokens: int = 10000,
        summary_threshold: float = 0.8,
        keep_recent_messages: int = 10,
        on_summary_needed: Optional[Callable[[List[BaseMessage]], Awaitable[str]]] = None,
        on_store_summary: Optional[Callable[[str, int], Awaitable[None]]] = None,
    ):
        self.config = MemoryConfig(
            max_tokens=max_tokens,
            summary_threshold=summary_threshold,
            keep_recent_messages=keep_recent_messages,
        )
        self.token_counter = TokenCounter()
        self.messages: List[BaseMessage] = []
        self.summaries: List[MemorySummary] = []
        self.on_summary_needed = on_summary_needed
        self.on_store_summary = on_store_summary
        self._summary_task: Optional[asyncio.Task] = None
        self._pending_summary: bool = False
    
    @property
    def current_tokens(self) -> int:
        return self.token_counter.count_messages(self.messages)
    
    @property
    def utilization(self) -> float:
        return self.current_tokens / self.config.max_tokens
    
    @property
    def needs_summary(self) -> bool:
        return self.utilization >= self.config.summary_threshold
    
    def add_short_term_memory(self, message: BaseMessage) -> None:
        content_preview = message.content[:100] + "..." if len(message.content) > 100 else message.content
        role = message.type if hasattr(message, 'type') else 'unknown'
        
        with memory_trace_step("add_short_term_memory", "short_term", {
            "role": role,
            "content_len": len(message.content),
            "content_preview": content_preview,
            "total_messages": len(self.messages) + 1,
            "total_tokens": self.current_tokens + len(message.content) // 2,
        }):
            self.messages.append(message)
            
            if self.current_tokens > self.config.max_tokens:
                self._enforce_limit()
            
            if self.needs_summary:
                self._pending_summary = True
    
    def add_messages(self, messages: List[BaseMessage]) -> None:
        total_content_len = sum(len(msg.content) for msg in messages)
        
        with memory_trace_step("add_messages", "short_term", {
            "count": len(messages),
            "total_content_len": total_content_len,
            "total_messages": len(self.messages) + len(messages),
        }):
            self.messages.extend(messages)
            
            if self.current_tokens > self.config.max_tokens:
                self._enforce_limit()
            
            if self.needs_summary:
                self._pending_summary = True
    
    def _enforce_limit(self) -> None:
        while self.current_tokens > self.config.max_tokens and len(self.messages) > self.config.keep_recent_messages:
            self.messages.pop(0)
    
    async def check_and_summarize(self, force: bool = False) -> Optional[MemorySummary]:
        with memory_trace_step("check_and_summarize", "summary", {"force": force, "needs_summary": self.needs_summary}):
            if not self.on_summary_needed:
                return None
            
            if not force and not self._pending_summary:
                return None
            
            if not self.needs_summary and not force:
                self._pending_summary = False
                return None
            
            messages_to_summarize = self.messages[:-self.config.keep_recent_messages]
            if not messages_to_summarize:
                self._pending_summary = False
                return None
            
            try:
                with memory_trace_step("generate_summary", "summary", {"message_count": len(messages_to_summarize)}):
                    summary_content = await self.on_summary_needed(messages_to_summarize)
                
                summary = MemorySummary(
                    id=str(uuid.uuid4()),
                    content=summary_content,
                    token_count=self.token_counter.count_text(summary_content),
                    message_range=(0, len(messages_to_summarize)),
                    created_at=datetime.now(timezone.utc),
                )
                
                self.summaries.append(summary)
                
                self.messages = self.messages[-self.config.keep_recent_messages:]
                
                self._pending_summary = False
                
                logger.info(f"Summary generated: {summary.token_count} tokens, {len(messages_to_summarize)} messages summarized")
                
                if self.on_store_summary:
                    try:
                        with memory_trace_step("store_summary_to_long_term", "long_term", {"summary_len": len(summary_content)}):
                            await self.on_store_summary(summary_content, len(messages_to_summarize))
                        logger.info("Summary synced to long-term memory")
                    except Exception as e:
                        logger.error(f"Failed to sync summary to long-term memory: {e}")
                
                return summary
                
            except Exception as e:
                logger.error(f"Summary generation failed: {e}")
                return None
    
    async def finalize_conversation(
        self,
        user_message: str,
        assistant_message: str,
        on_store_long_term: Optional[Callable[[str, str, int], Awaitable[None]]] = None,
    ) -> dict:
        with memory_trace_step("finalize_conversation", "short_term", {
            "user_msg_len": len(user_message),
            "assistant_msg_len": len(assistant_message),
            "needs_summary": self.needs_summary,
        }):
            self.add_short_term_memory(HumanMessage(content=user_message))
            self.add_short_term_memory(AIMessage(content=assistant_message))
            
            result = {
                "summary_generated": False,
                "summary": None,
                "stored_to_long_term": False,
            }
            
            if self.needs_summary:
                summary = await self.check_and_summarize()
                if summary:
                    result["summary_generated"] = True
                    result["summary"] = summary
            
            if on_store_long_term:
                try:
                    await on_store_long_term(user_message, assistant_message, 3)
                    result["stored_to_long_term"] = True
                except Exception as e:
                    logger.error(f"Failed to store to long-term memory: {e}")
            
            return result
    
    def get_context(self, max_tokens: Optional[int] = None) -> List[BaseMessage]:
        max_tokens = max_tokens or self.config.max_tokens
        
        with memory_trace_step("get_context", "short_term", {
            "max_tokens": max_tokens,
            "summaries_count": len(self.summaries),
            "messages_count": len(self.messages),
            "total_tokens": self.current_tokens,
        }):
            context = []
            
            for summary in self.summaries[-3:]:
                summary_msg = SystemMessage(content=f"[对话摘要] {summary.content}")
                context.append(summary_msg)
            
            remaining_tokens = max_tokens - self.token_counter.count_messages(context)
            
            recent_messages = self.token_counter.truncate_messages(
                self.messages,
                remaining_tokens,
                preserve_system=False,
            )
            
            context.extend(recent_messages)
            
            return context
    
    def clear(self) -> None:
        self.messages = []
        self.summaries = []
        self._pending_summary = False
    
    def get_stats(self) -> dict:
        return {
            "message_count": len(self.messages),
            "summary_count": len(self.summaries),
            "current_tokens": self.current_tokens,
            "max_tokens": self.config.max_tokens,
            "utilization": f"{self.utilization:.1%}",
            "pending_summary": self._pending_summary,
        }

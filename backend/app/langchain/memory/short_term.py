from typing import List, Optional, Callable, Awaitable
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from pydantic import BaseModel
from datetime import datetime
import asyncio
import uuid

from .token_counter import TokenCounter


class MemoryConfig(BaseModel):
    max_tokens: int = 10000
    summary_threshold: float = 0.8
    keep_recent_messages: int = 5


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
        keep_recent_messages: int = 5,
        on_summary_needed: Optional[Callable[[List[BaseMessage]], Awaitable[str]]] = None,
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
        self._summary_task: Optional[asyncio.Task] = None
    
    @property
    def current_tokens(self) -> int:
        return self.token_counter.count_messages(self.messages)
    
    @property
    def utilization(self) -> float:
        return self.current_tokens / self.config.max_tokens
    
    @property
    def needs_summary(self) -> bool:
        return self.utilization >= self.config.summary_threshold
    
    def add_message(self, message: BaseMessage) -> None:
        self.messages.append(message)
        
        if self.current_tokens > self.config.max_tokens:
            self._enforce_limit()
        
        if self.needs_summary and self.on_summary_needed:
            self._trigger_async_summary()
    
    def add_messages(self, messages: List[BaseMessage]) -> None:
        self.messages.extend(messages)
        
        if self.current_tokens > self.config.max_tokens:
            self._enforce_limit()
        
        if self.needs_summary and self.on_summary_needed:
            self._trigger_async_summary()
    
    def _enforce_limit(self) -> None:
        while self.current_tokens > self.config.max_tokens and len(self.messages) > self.config.keep_recent_messages:
            self.messages.pop(0)
    
    def _trigger_async_summary(self) -> None:
        if self._summary_task and not self._summary_task.done():
            return
        
        messages_to_summarize = self.messages[:-self.config.keep_recent_messages]
        if not messages_to_summarize:
            return
        
        self._summary_task = asyncio.create_task(
            self._async_summarize(messages_to_summarize)
        )
    
    async def _async_summarize(self, messages: List[BaseMessage]) -> None:
        try:
            summary_content = await self.on_summary_needed(messages)
            
            summary = MemorySummary(
                id=str(uuid.uuid4()),
                content=summary_content,
                token_count=self.token_counter.count_text(summary_content),
                message_range=(0, len(messages)),
                created_at=datetime.utcnow(),
            )
            
            self.summaries.append(summary)
            
            self.messages = self.messages[-self.config.keep_recent_messages:]
            
        except Exception as e:
            print(f"Summary generation failed: {e}")
    
    def get_context(self, max_tokens: Optional[int] = None) -> List[BaseMessage]:
        max_tokens = max_tokens or self.config.max_tokens
        
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
    
    def get_stats(self) -> dict:
        return {
            "message_count": len(self.messages),
            "summary_count": len(self.summaries),
            "current_tokens": self.current_tokens,
            "max_tokens": self.config.max_tokens,
            "utilization": f"{self.utilization:.1%}",
        }

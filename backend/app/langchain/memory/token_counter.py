from typing import List, Union
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage


class TokenCounter:
    def __init__(self, model: str = "gpt-4"):
        self.model = model
        self._encoding = None
    
    @property
    def encoding(self):
        if self._encoding is None:
            try:
                import tiktoken
                model_name = "cl100k_base" if "gpt" in self.model.lower() else "cl100k_base"
                self._encoding = tiktoken.get_encoding(model_name)
            except ImportError:
                self._encoding = None
        return self._encoding
    
    def count_text(self, text: str) -> int:
        if not text:
            return 0
        
        if self.encoding:
            return len(self.encoding.encode(text))
        
        return self._estimate_tokens(text)
    
    def _estimate_tokens(self, text: str) -> int:
        char_count = len(text)
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        non_chinese = char_count - chinese_chars
        
        return int(chinese_chars * 1.5 + non_chinese / 4)
    
    def count_message(self, message: BaseMessage) -> int:
        tokens = 4
        tokens += self.count_text(message.content or "")
        
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tc in message.tool_calls:
                tokens += self.count_text(str(tc))
        
        return tokens
    
    def count_messages(self, messages: List[BaseMessage]) -> int:
        return sum(self.count_message(msg) for msg in messages)
    
    def truncate_messages(
        self,
        messages: List[BaseMessage],
        max_tokens: int,
        preserve_system: bool = True,
    ) -> List[BaseMessage]:
        if self.count_messages(messages) <= max_tokens:
            return messages
        
        result = []
        system_messages = []
        
        if preserve_system:
            system_messages = [m for m in messages if isinstance(m, SystemMessage)]
            other_messages = [m for m in messages if not isinstance(m, SystemMessage)]
        else:
            other_messages = messages
        
        system_tokens = self.count_messages(system_messages)
        remaining_tokens = max_tokens - system_tokens
        
        truncated = []
        current_tokens = 0
        
        for msg in reversed(other_messages):
            msg_tokens = self.count_message(msg)
            if current_tokens + msg_tokens <= remaining_tokens:
                truncated.insert(0, msg)
                current_tokens += msg_tokens
            else:
                break
        
        return system_messages + truncated

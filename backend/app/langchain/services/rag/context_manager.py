"""
对话上下文管理模块

功能：
1. 滑动窗口管理对话历史
2. 关键实体缓存
3. 对话上下文提取
"""
from typing import List, Optional, Any
import re
import logging

from .rag_types import ConversationTurn

logger = logging.getLogger(__name__)


class EntityExtractor:
    """
    实体提取器
    
    从文本中提取关键实体，用于查询重写
    """
    
    CHINESE_ENTITY_PATTERNS = [
        (r'[\u4e00-\u9fff]+(?:公司|集团|企业|银行|机构)', 'ORG'),
        (r'[\u4e00-\u9fff]+(?:手机|电脑|汽车|产品|服务)', 'PRODUCT'),
        (r'[\u4e00-\u9fff]+(?:技术|框架|语言|算法)', 'TECH'),
        (r'[A-Z][a-z]+(?:Inc|Corp|Ltd|LLC)?', 'ORG_EN'),
        (r'\d{4}年\d{1,2}月\d{1,2}日', 'DATE'),
        (r'\d+(?:\.\d+)?(?:亿|万|千|百)', 'NUMBER'),
    ]
    
    def __init__(self):
        self._patterns = [(re.compile(p), t) for p, t in self.CHINESE_ENTITY_PATTERNS]
    
    def extract(self, text: str) -> List[str]:
        """提取文本中的实体"""
        entities = []
        
        for pattern, entity_type in self._patterns:
            matches = pattern.findall(text)
            entities.extend(matches)
        
        entities = list(set(entities))
        
        return entities
    
    def extract_from_history(
        self,
        history: List[ConversationTurn],
        max_entities: int = 10,
    ) -> List[str]:
        """从对话历史中提取实体"""
        all_entities = []
        
        for turn in reversed(history):
            entities = self.extract(turn.content)
            all_entities.extend(entities)
        
        seen = set()
        unique_entities = []
        for e in all_entities:
            if e not in seen:
                seen.add(e)
                unique_entities.append(e)
        
        return unique_entities[:max_entities]


class ContextManager:
    """
    对话上下文管理器
    
    功能：
    1. 滑动窗口管理对话历史
    2. 关键实体缓存
    3. 对话摘要生成
    """
    
    def __init__(
        self,
        max_turns: int = 10,
        max_tokens: int = 4000,
        token_counter: Optional[Any] = None,
    ):
        self.max_turns = max_turns
        self.max_tokens = max_tokens
        self.token_counter = token_counter
        
        self._history: List[ConversationTurn] = []
        self._entity_cache: List[str] = []
        self._summary: Optional[str] = None
        self._entity_extractor = EntityExtractor()
    
    def add_message(
        self,
        role: str,
        content: str,
        intent: Optional[str] = None,
    ) -> None:
        """添加消息到历史"""
        entities = self._entity_extractor.extract(content)
        
        turn = ConversationTurn(
            role=role,
            content=content,
            entities=entities,
            intent=intent,
        )
        
        self._history.append(turn)
        
        for entity in entities:
            if entity not in self._entity_cache:
                self._entity_cache.append(entity)
        
        while len(self._history) > self.max_turns:
            removed = self._history.pop(0)
        
        self._enforce_token_limit()
    
    def _enforce_token_limit(self) -> None:
        """确保历史不超过 Token 限制"""
        if not self.token_counter:
            return
        
        while self._history:
            total_tokens = sum(
                self.token_counter.count_tokens(turn.content)
                for turn in self._history
            )
            if total_tokens <= self.max_tokens:
                break
            self._history.pop(0)
    
    def get_history(self, limit: Optional[int] = None) -> List[ConversationTurn]:
        """获取对话历史"""
        if limit:
            return self._history[-limit:]
        return self._history.copy()
    
    def get_entities(self) -> List[str]:
        """获取缓存的实体"""
        return self._entity_cache.copy()
    
    def get_context_for_query(
        self,
        query: str,
        max_turns: Optional[int] = None,
    ) -> str:
        """
        获取与查询相关的上下文
        
        返回格式化的对话历史字符串
        """
        max_turns = max_turns or self.max_turns
        relevant_history = self._history[-max_turns:]
        
        if not relevant_history:
            return ""
        
        context_parts = []
        for turn in relevant_history:
            prefix = "用户" if turn.role == "user" else "助手"
            context_parts.append(f"{prefix}: {turn.content}")
        
        return "\n".join(context_parts)
    
    def clear(self) -> None:
        """清空历史"""
        self._history.clear()
        self._entity_cache.clear()
        self._summary = None
    
    def get_last_user_query(self) -> Optional[str]:
        """获取最后一个用户查询"""
        for turn in reversed(self._history):
            if turn.role == "user":
                return turn.content
        return None
    
    def get_last_assistant_response(self) -> Optional[str]:
        """获取最后一个助手响应"""
        for turn in reversed(self._history):
            if turn.role == "assistant":
                return turn.content
        return None
    
    def update_last_user_message(
        self,
        original: str,
        rewritten: str,
    ) -> None:
        """
        更新最后一个用户消息
        
        记录查询重写信息，用于后续上下文理解
        
        Args:
            original: 原始查询
            rewritten: 重写后的查询
        """
        for turn in reversed(self._history):
            if turn.role == "user" and turn.content == original:
                turn.content = rewritten
                turn.intent = "rewritten"
                break
    
    def add_user_message(self, content: str, intent: Optional[str] = None) -> None:
        """添加用户消息"""
        self.add_message("user", content, intent)
    
    def add_assistant_message(self, content: str, intent: Optional[str] = None) -> None:
        """添加助手消息"""
        self.add_message("assistant", content, intent)


ConversationHistoryManager = ContextManager

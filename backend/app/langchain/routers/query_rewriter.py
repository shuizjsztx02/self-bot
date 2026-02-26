"""
查询重写模块

功能：
1. 查询重写 - 将依赖上下文的查询转换为独立查询
2. 查询扩展 - 生成多个查询变体提高召回率
3. 实体提取 - 从对话历史中提取关键实体
"""
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
import re
import logging
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class QueryRewriteConfig:
    """查询重写配置"""
    max_history_turns: int = 5
    max_query_variations: int = 3
    enable_entity_extraction: bool = True
    enable_query_expansion: bool = True


@dataclass
class ConversationTurn:
    """对话轮次"""
    role: str  # "user" or "assistant"
    content: str
    entities: List[str] = field(default_factory=list)
    intent: Optional[str] = None


@dataclass
class RewrittenQuery:
    """重写后的查询"""
    original_query: str
    rewritten_query: str
    variations: List[str] = field(default_factory=list)
    extracted_entities: List[str] = field(default_factory=list)
    confidence: float = 1.0


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


class PronounResolver:
    """
    代词解析器
    
    识别并解析查询中的代词，替换为具体实体
    """
    
    CHINESE_PRONOUNS = {
        '它': 'entity',
        '它们': 'entities',
        '这个': 'entity',
        '那个': 'entity',
        '这': 'entity',
        '那': 'entity',
        '其': 'entity',
        '该': 'entity',
        '此': 'entity',
    }
    
    ENGLISH_PRONOUNS = {
        'it': 'entity',
        'they': 'entities',
        'this': 'entity',
        'that': 'entity',
        'these': 'entities',
        'those': 'entities',
    }
    
    def __init__(self):
        self._all_pronouns = {**self.CHINESE_PRONOUNS, **self.ENGLISH_PRONOUNS}
    
    def detect_pronouns(self, query: str) -> List[Tuple[str, str]]:
        """检测查询中的代词"""
        detected = []
        query_lower = query.lower()
        
        for pronoun, ptype in self._all_pronouns.items():
            if pronoun in query_lower or pronoun in query:
                detected.append((pronoun, ptype))
        
        return detected
    
    def resolve(
        self,
        query: str,
        entities: List[str],
        history: List[ConversationTurn],
    ) -> Tuple[str, float]:
        """
        解析代词，返回重写后的查询
        
        Returns:
            (rewritten_query, confidence)
        """
        pronouns = self.detect_pronouns(query)
        
        if not pronouns:
            return query, 1.0
        
        if not entities and history:
            extractor = EntityExtractor()
            entities = extractor.extract_from_history(history)
        
        if not entities:
            return query, 0.5
        
        rewritten = query
        confidence = 1.0
        
        for pronoun, ptype in pronouns:
            if ptype == 'entity' and entities:
                replacement = entities[0]
                rewritten = rewritten.replace(pronoun, replacement)
                confidence *= 0.9
            elif ptype == 'entities' and len(entities) > 1:
                replacement = '、'.join(entities[:3])
                rewritten = rewritten.replace(pronoun, replacement)
                confidence *= 0.85
        
        return rewritten, confidence


class QueryExpander:
    """
    查询扩展器
    
    生成多个查询变体，提高检索召回率
    """
    
    SYNONYM_MAP = {
        '股票': ['股价', '股市', '证券'],
        '价格': ['价钱', '费用', '成本'],
        '公司': ['企业', '机构', '组织'],
        '产品': ['商品', '货物', '物品'],
        '技术': ['技术方案', '技术架构', '实现方式'],
        '问题': ['疑问', '困惑', '难题'],
        '方法': ['方式', '途径', '办法'],
        '分析': ['研究', '解析', '探讨'],
    }
    
    def expand(self, query: str, max_variations: int = 3) -> List[str]:
        """
        扩展查询，生成变体
        
        策略：
        1. 同义词替换
        2. 关键词提取
        3. 实体聚焦
        """
        variations = []
        
        for term, synonyms in self.SYNONYM_MAP.items():
            if term in query:
                for synonym in synonyms[:2]:
                    variation = query.replace(term, synonym)
                    if variation != query:
                        variations.append(variation)
        
        variations = list(set(variations))[:max_variations]
        
        return variations


class QueryRewriter:
    """
    查询重写器
    
    整合所有重写策略，提供统一的查询重写接口
    """
    
    def __init__(
        self,
        config: Optional[QueryRewriteConfig] = None,
        llm_client: Optional[Any] = None,
    ):
        self.config = config or QueryRewriteConfig()
        self.llm_client = llm_client
        self.entity_extractor = EntityExtractor()
        self.pronoun_resolver = PronounResolver()
        self.query_expander = QueryExpander()
    
    async def rewrite(
        self,
        query: str,
        history: Optional[List[ConversationTurn]] = None,
    ) -> RewrittenQuery:
        """
        重写查询
        
        Args:
            query: 原始查询
            history: 对话历史
        
        Returns:
            RewrittenQuery 对象
        """
        history = history or []
        
        entities = []
        if self.config.enable_entity_extraction:
            entities = self.entity_extractor.extract_from_history(history)
        
        rewritten_query, confidence = self.pronoun_resolver.resolve(
            query, entities, history
        )
        
        if self.llm_client and len(history) > 0:
            rewritten_query = await self._llm_rewrite(query, history, rewritten_query)
        
        variations = []
        if self.config.enable_query_expansion:
            variations = self.query_expander.expand(
                rewritten_query,
                self.config.max_query_variations,
            )
        
        return RewrittenQuery(
            original_query=query,
            rewritten_query=rewritten_query,
            variations=variations,
            extracted_entities=entities,
            confidence=confidence,
        )
    
    async def _llm_rewrite(
        self,
        query: str,
        history: List[ConversationTurn],
        fallback_query: str,
    ) -> str:
        """使用 LLM 进行更智能的查询重写"""
        if not self.llm_client:
            return fallback_query
        
        history_text = "\n".join([
            f"{turn.role}: {turn.content}"
            for turn in history[-self.config.max_history_turns:]
        ])
        
        prompt = f"""基于以下对话历史，将用户的最新问题重写为一个独立、完整的问题。
不要添加回答，只返回重写后的问题。

对话历史：
{history_text}

用户最新问题：{query}

重写后的问题："""
        
        try:
            if hasattr(self.llm_client, 'ainvoke'):
                response = await self.llm_client.ainvoke(prompt)
                if hasattr(response, 'content'):
                    return response.content.strip()
                return str(response).strip()
            else:
                return fallback_query
        except Exception as e:
            logger.warning(f"LLM rewrite failed: {e}")
            return fallback_query
    
    def create_turn(
        self,
        role: str,
        content: str,
        intent: Optional[str] = None,
    ) -> ConversationTurn:
        """创建对话轮次"""
        entities = []
        if self.config.enable_entity_extraction:
            entities = self.entity_extractor.extract(content)
        
        return ConversationTurn(
            role=role,
            content=content,
            entities=entities,
            intent=intent,
        )


class ConversationHistoryManager:
    """
    对话历史管理器
    
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

"""
查询重写模块

功能：
1. 查询重写 - 将依赖上下文的查询转换为独立查询
2. 查询扩展 - 生成多个查询变体提高召回率
3. 代词解析 - 识别并解析查询中的代词
"""
from typing import List, Optional, Any, Tuple
import logging

from .rag_types import (
    ConversationTurn,
    RewrittenQuery,
    QueryRewriteConfig,
)
from .context_manager import EntityExtractor

logger = logging.getLogger(__name__)


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

from enum import Enum
from pydantic import BaseModel
from typing import Optional, List, Dict
import re
import time
import logging
from collections import defaultdict

from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class QueryIntent(str, Enum):
    GENERAL_CHAT = "general_chat"
    CODE_TASK = "code_task"
    SEARCH_TASK = "search_task"
    KB_QUERY = "kb_query"
    TOOL_TASK = "tool_task"
    DOCUMENT_TASK = "document_task"
    DATA_ANALYSIS = "data_analysis"
    AMBIGUOUS = "ambiguous"


class IntentResult(BaseModel):
    intent: QueryIntent
    confidence: float
    kb_hints: List[str] = []
    reasoning: str = ""
    secondary_intents: List[Dict] = []


class DynamicThreshold:
    """动态置信度阈值管理器"""
    
    def __init__(self):
        self._history: Dict[str, List[bool]] = defaultdict(list)
        self._base_thresholds = {
            QueryIntent.CODE_TASK: 0.85,
            QueryIntent.SEARCH_TASK: 0.80,
            QueryIntent.KB_QUERY: 0.75,
            QueryIntent.TOOL_TASK: 0.80,
            QueryIntent.DOCUMENT_TASK: 0.75,
            QueryIntent.DATA_ANALYSIS: 0.75,
            QueryIntent.GENERAL_CHAT: 0.60,
            QueryIntent.AMBIGUOUS: 0.50,
        }
        self._adjustment_factor = 0.05
        self._history_size = 100
    
    def get_threshold(self, intent: QueryIntent) -> float:
        """获取动态阈值"""
        base = self._base_thresholds.get(intent, 0.70)
        
        history = self._history.get(intent.value, [])
        if len(history) < 10:
            return base
        
        accuracy = sum(history[-50:]) / len(history[-50:])
        
        if accuracy > 0.85:
            return base - self._adjustment_factor
        elif accuracy < 0.65:
            return base + self._adjustment_factor
        
        return base
    
    def record_result(self, intent: QueryIntent, correct: bool):
        """记录分类结果准确性"""
        self._history[intent.value].append(correct)
        if len(self._history[intent.value]) > self._history_size:
            self._history[intent.value] = self._history[intent.value][-self._history_size:]
    
    def get_parallel_threshold(self) -> float:
        """获取并行路由的置信度阈值"""
        return 0.65


class IntentClassifier:
    """
    意图分类器
    
    使用多阶段策略：
    1. 规则快速过滤
    2. 关键词匹配
    3. LLM语义分类
    4. 动态阈值调整
    """
    
    CODE_PATTERNS = [
        r"写(一个|段|个).*代码",
        r"帮我写.*程序",
        r"编程|代码|脚本",
        r"python|java|javascript|go|rust|typescript",
        r"函数|类|方法|接口|模块",
        r"debug|调试|修复.*bug",
        r"优化.*代码",
        r"实现.*功能",
        r"重构.*代码",
    ]
    
    SEARCH_PATTERNS = [
        r"搜索|查一下|找一下|搜一下",
        r"最新|最近|新闻",
        r"新闻|热点|事件",
        r"什么是|什么是.*意思",
        r"如何.*设置|如何.*安装",
        r"比较.*区别",
        r"评测|评价|测评",
    ]
    
    KB_PATTERNS = [
        r"公司.*制度|流程|规定|政策",
        r"产品.*手册|文档|说明|指南",
        r"项目.*方案|报告|文档",
        r"知识库|文档库|资料库",
        r"内部.*文档|资料",
        r"报销|请假|考勤",
        r"财务|预算|审批",
        r"self-bot|面试",
    ]
    
    DOCUMENT_PATTERNS = [
        r"创建.*文档|新建.*文档",
        r"编辑.*文档|修改.*文档",
        r"生成.*ppt|制作.*ppt|创建.*ppt",
        r"生成.*word|创建.*word",
        r"生成.*excel|创建.*excel",
        r"转换.*格式",
        r"提取.*文字|提取.*内容",
    ]
    
    DATA_PATTERNS = [
        r"分析.*数据|数据分析",
        r"统计.*结果|统计.*数据",
        r"生成.*报表|创建.*报表",
        r"可视化|图表|绘图",
        r"计算.*平均值|计算.*总和",
    ]
    
    DEFAULT_KB_KEYWORDS = {
        "财务": ["财务知识库"],
        "报销": ["财务知识库"],
        "预算": ["财务知识库"],
        "制度": ["公司制度库"],
        "流程": ["公司制度库"],
        "规定": ["公司制度库"],
        "产品": ["产品文档库"],
        "手册": ["产品文档库"],
        "说明书": ["产品文档库"],
        "技术": ["技术文档库"],
        "API": ["技术文档库"],
        "开发": ["技术文档库"],
        "项目": ["项目文档库"],
        "方案": ["项目文档库"],
    }
    
    KB_CACHE_TTL = 300
    
    def __init__(self, llm: ChatOpenAI, db_session=None):
        self.llm = llm
        self.dynamic_threshold = DynamicThreshold()
        self.db_session = db_session
        self._kb_keywords_cache = None
        self._kb_keywords_last_refresh = 0
    
    async def _ensure_kb_keywords(self):
        """确保知识库关键词已加载（带缓存过期检查）"""
        current_time = time.time()
        cache_expired = (
            self._kb_keywords_cache is None or
            (current_time - self._kb_keywords_last_refresh) > self.KB_CACHE_TTL
        )
        
        if cache_expired:
            if self._kb_keywords_cache is None:
                logger.info("[IntentClassifier] KB keywords cache not initialized, refreshing...")
            else:
                logger.info(f"[IntentClassifier] KB keywords cache expired (TTL={self.KB_CACHE_TTL}s), refreshing...")
            await self.refresh_kb_keywords()
        
        return self._kb_keywords_cache or self.DEFAULT_KB_KEYWORDS
    
    async def refresh_kb_keywords(self, force: bool = False):
        """
        从数据库刷新知识库关键词映射
        
        Args:
            force: 是否强制刷新（忽略缓存）
        """
        if not self.db_session:
            logger.info("[IntentClassifier] No db_session provided, using default KB_KEYWORDS")
            self._kb_keywords_cache = self.DEFAULT_KB_KEYWORDS.copy()
            return
        
        try:
            from sqlalchemy import select
            from app.knowledge_base.models import KnowledgeBase
            
            result = await self.db_session.execute(
                select(KnowledgeBase.id, KnowledgeBase.name)
                .where(KnowledgeBase.is_active == True)
            )
            kbs = result.all()
            
            self._kb_keywords_cache = {}
            
            for kb_id, kb_name in kbs:
                keywords = self._extract_keywords_from_name(kb_name)
                for keyword in keywords:
                    if keyword not in self._kb_keywords_cache:
                        self._kb_keywords_cache[keyword] = []
                    self._kb_keywords_cache[keyword].append(kb_name)
            
            self._kb_keywords_last_refresh = time.time()
            logger.info(f"[IntentClassifier] Refreshed KB keywords: {len(self._kb_keywords_cache)} keywords from {len(kbs)} knowledge bases")
            logger.debug(f"[IntentClassifier] KB keywords mapping: {self._kb_keywords_cache}")
            
        except Exception as e:
            logger.warning(f"[IntentClassifier] Failed to refresh KB keywords: {e}, using defaults")
            self._kb_keywords_cache = self.DEFAULT_KB_KEYWORDS.copy()
    
    def _extract_keywords_from_name(self, name: str) -> List[str]:
        """从知识库名称中提取关键词"""
        keywords = []
        
        common_suffixes = ["知识库", "文档库", "资料库", "库", "文档", "资料"]
        cleaned_name = name
        for suffix in common_suffixes:
            cleaned_name = cleaned_name.replace(suffix, "")
        
        if cleaned_name and len(cleaned_name) >= 2:
            keywords.append(cleaned_name)
        
        import re
        chinese_words = re.findall(r'[\u4e00-\u9fa5]+', name)
        for word in chinese_words:
            if len(word) >= 2:
                keywords.append(word)
        
        return list(set(keywords))
    
    async def classify(self, query: str) -> IntentResult:
        """
        分类用户意图
        """
        logger.info(f"[IntentClassifier] Classifying: '{query[:50]}...'")
        
        rule_result = self._rule_filter(query)
        if rule_result:
            threshold = self.dynamic_threshold.get_threshold(rule_result.intent)
            if rule_result.confidence >= threshold:
                logger.info(f"[IntentClassifier] Rule matched: {rule_result.intent.value}, confidence={rule_result.confidence:.2f}, reasoning={rule_result.reasoning}")
                
                if rule_result.intent == QueryIntent.KB_QUERY and not rule_result.kb_hints:
                    keyword_result = await self._keyword_match(query)
                    if keyword_result and keyword_result.kb_hints:
                        rule_result.kb_hints = keyword_result.kb_hints
                        logger.info(f"[IntentClassifier] Enriched kb_hints from keyword match: {rule_result.kb_hints}")
                
                return rule_result
        
        keyword_result = await self._keyword_match(query)
        if keyword_result:
            threshold = self.dynamic_threshold.get_threshold(keyword_result.intent)
            if keyword_result.confidence >= threshold:
                logger.info(f"[IntentClassifier] Keyword matched: {keyword_result.intent.value}, confidence={keyword_result.confidence:.2f}, kb_hints={keyword_result.kb_hints}")
                return keyword_result
        
        logger.info(f"[IntentClassifier] No rule/keyword match, using LLM classification")
        llm_result = await self._llm_classify(query)
        logger.info(f"[IntentClassifier] LLM result: {llm_result.intent.value}, confidence={llm_result.confidence:.2f}")
        
        return llm_result
    
    async def classify_with_alternatives(self, query: str) -> IntentResult:
        """
        分类用户意图，同时返回备选意图
        
        用于并行路由决策
        """
        result = await self.classify(query)
        
        parallel_threshold = self.dynamic_threshold.get_parallel_threshold()
        
        if result.confidence < parallel_threshold:
            alternatives = await self._get_alternative_intents(query, result)
            result.secondary_intents = alternatives
        
        return result
    
    async def _get_alternative_intents(self, query: str, primary: IntentResult) -> List[Dict]:
        """获取备选意图"""
        alternatives = []
        
        rule_result = self._rule_filter(query)
        if rule_result and rule_result.intent != primary.intent:
            alternatives.append({
                "intent": rule_result.intent.value,
                "confidence": rule_result.confidence,
                "route": self._intent_to_route(rule_result.intent),
            })
        
        keyword_result = await self._keyword_match(query)
        if keyword_result and keyword_result.intent != primary.intent:
            alternatives.append({
                "intent": keyword_result.intent.value,
                "confidence": keyword_result.confidence,
                "route": self._intent_to_route(keyword_result.intent),
            })
        
        alternatives.sort(key=lambda x: x["confidence"], reverse=True)
        
        return alternatives[:2]
    
    def _intent_to_route(self, intent: QueryIntent) -> str:
        """将意图转换为路由"""
        route_map = {
            QueryIntent.KB_QUERY: "rag_first",
            QueryIntent.SEARCH_TASK: "research_first",
            QueryIntent.DOCUMENT_TASK: "tool_first",
            QueryIntent.DATA_ANALYSIS: "tool_first",
            QueryIntent.CODE_TASK: "direct",
            QueryIntent.TOOL_TASK: "direct",
            QueryIntent.GENERAL_CHAT: "direct",
            QueryIntent.AMBIGUOUS: "parallel",
        }
        return route_map.get(intent, "direct")
    
    def _rule_filter(self, query: str) -> Optional[IntentResult]:
        """规则快速过滤"""
        
        for pattern in self.DOCUMENT_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return IntentResult(
                    intent=QueryIntent.DOCUMENT_TASK,
                    confidence=0.92,
                    reasoning=f"匹配文档操作模式: {pattern}",
                )
        
        for pattern in self.DATA_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return IntentResult(
                    intent=QueryIntent.DATA_ANALYSIS,
                    confidence=0.90,
                    reasoning=f"匹配数据分析模式: {pattern}",
                )
        
        for pattern in self.CODE_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return IntentResult(
                    intent=QueryIntent.CODE_TASK,
                    confidence=0.95,
                    reasoning=f"匹配代码模式: {pattern}",
                )
        
        for pattern in self.KB_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return IntentResult(
                    intent=QueryIntent.KB_QUERY,
                    confidence=0.85,
                    reasoning=f"匹配知识库模式: {pattern}",
                )
        
        for pattern in self.SEARCH_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return IntentResult(
                    intent=QueryIntent.SEARCH_TASK,
                    confidence=0.90,
                    reasoning=f"匹配搜索模式: {pattern}",
                )
        
        return None
    
    async def _keyword_match(self, query: str) -> Optional[IntentResult]:
        """关键词匹配"""
        kb_keywords = await self._ensure_kb_keywords()
        
        matched_kbs = []
        for keyword, kbs in kb_keywords.items():
            if keyword in query:
                matched_kbs.extend(kbs)
        
        if matched_kbs:
            return IntentResult(
                intent=QueryIntent.KB_QUERY,
                confidence=0.75,
                kb_hints=list(set(matched_kbs)),
                reasoning="匹配知识库关键词",
            )
        
        return None
    
    async def _llm_classify(self, query: str) -> IntentResult:
        """LLM语义分类"""
        
        prompt = f"""分析用户问题的意图，返回JSON格式的结果。

用户问题：{query}

返回格式：
{{
    "intent": "意图类别",
    "confidence": 0.0-1.0,
    "kb_hints": ["可能相关的知识库"],
    "reasoning": "判断理由"
}}

意图类别：
- general_chat: 日常闲聊、问候、简单问答
- code_task: 编程、代码相关任务
- search_task: 需要互联网搜索获取最新信息
- kb_query: 查询内部知识库、文档、制度等
- tool_task: 需要使用特定工具（文件操作、计算等）
- document_task: 创建、编辑文档（Word、PPT、Excel等）
- data_analysis: 数据分析、统计、可视化
- ambiguous: 意图不明确，需要更多信息

只返回JSON，不要其他内容。"""

        try:
            response = await self.llm.ainvoke(prompt)
            
            import json
            content = response.content.strip()
            if content.startswith("```"):
                content = content.strip("`").strip()
                if content.startswith("json"):
                    content = content[4:].strip()
            
            result = json.loads(content)
            
            return IntentResult(
                intent=QueryIntent(result.get("intent", "ambiguous")),
                confidence=result.get("confidence", 0.5),
                kb_hints=result.get("kb_hints", []),
                reasoning=result.get("reasoning", ""),
            )
        except Exception as e:
            return IntentResult(
                intent=QueryIntent.AMBIGUOUS,
                confidence=0.3,
                reasoning=f"LLM分类失败: {str(e)}",
            )
    
    def record_feedback(self, intent: QueryIntent, correct: bool):
        """记录用户反馈，用于动态调整阈值"""
        self.dynamic_threshold.record_result(intent, correct)

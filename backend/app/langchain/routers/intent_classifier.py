from enum import Enum
from pydantic import BaseModel
from typing import Optional, List, Dict
import re
import time
from collections import defaultdict

from langchain_openai import ChatOpenAI


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
        r"最新|最近|今天.*新闻",
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
    
    KB_KEYWORDS = {
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
    
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.dynamic_threshold = DynamicThreshold()
    
    async def classify(self, query: str) -> IntentResult:
        """
        分类用户意图
        """
        rule_result = self._rule_filter(query)
        if rule_result:
            threshold = self.dynamic_threshold.get_threshold(rule_result.intent)
            if rule_result.confidence >= threshold:
                return rule_result
        
        keyword_result = self._keyword_match(query)
        if keyword_result:
            threshold = self.dynamic_threshold.get_threshold(keyword_result.intent)
            if keyword_result.confidence >= threshold:
                return keyword_result
        
        llm_result = await self._llm_classify(query)
        
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
        
        keyword_result = self._keyword_match(query)
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
        
        for pattern in self.SEARCH_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return IntentResult(
                    intent=QueryIntent.SEARCH_TASK,
                    confidence=0.90,
                    reasoning=f"匹配搜索模式: {pattern}",
                )
        
        for pattern in self.KB_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return IntentResult(
                    intent=QueryIntent.KB_QUERY,
                    confidence=0.85,
                    reasoning=f"匹配知识库模式: {pattern}",
                )
        
        return None
    
    def _keyword_match(self, query: str) -> Optional[IntentResult]:
        """关键词匹配"""
        
        matched_kbs = []
        for keyword, kbs in self.KB_KEYWORDS.items():
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

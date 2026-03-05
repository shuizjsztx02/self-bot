"""
模式识别引擎

从任务执行历史中识别重复模式，使用向量化和聚类算法
"""
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import asyncio
import logging
import json
from pathlib import Path

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_similarity

from .models import (
    TaskExecutionTrace,
    SkillPattern,
    TaskType,
    ExecutionStatus
)
from .config import evolution_settings

logger = logging.getLogger(__name__)


class PatternRecognizer:
    """模式识别引擎"""
    
    def __init__(
        self,
        vector_store=None,
        min_frequency: int = None,
        min_success_rate: float = None,
        similarity_threshold: float = None,
    ):
        self.vector_store = vector_store
        self.min_frequency = min_frequency or evolution_settings.PATTERN_MIN_FREQUENCY
        self.min_success_rate = min_success_rate or evolution_settings.PATTERN_MIN_SUCCESS_RATE
        self.similarity_threshold = similarity_threshold or evolution_settings.PATTERN_SIMILARITY_THRESHOLD
        
        # 轨迹存储路径 - 使用AGENT_TRACE_PATH
        from app.config import settings
        self.traces_dir = Path(settings.AGENT_TRACE_PATH)
        self.traces_dir.mkdir(parents=True, exist_ok=True)
    
    async def analyze_recent_traces(
        self,
        days: int = None,
        limit: int = 1000
    ) -> List[SkillPattern]:
        """
        分析最近的执行轨迹，识别可固化的模式
        
        Args:
            days: 分析最近几天的数据
            limit: 最大分析数量
            
        Returns:
            识别出的Skill模式列表
        """
        days = days or evolution_settings.EVOLUTION_ANALYSIS_DAYS
        logger.info(f"[PatternRecognizer] Analyzing traces from last {days} days")
        
        # 1. 加载执行轨迹
        traces = await self._load_traces(days, limit)
        if not traces:
            logger.warning("No traces found for analysis")
            return []
        
        logger.info(f"Loaded {len(traces)} traces for analysis")
        
        # 2. 向量化任务描述
        embeddings = await self._embed_traces(traces)
        
        # 3. 计算相似度矩阵
        similarity_matrix = cosine_similarity(embeddings)
        
        # 4. 聚类相似任务
        clusters = self._cluster_traces(similarity_matrix)
        
        # 5. 提取每个聚类的模式
        patterns = []
        for cluster_indices in clusters:
            cluster_traces = [traces[i] for i in cluster_indices]
            pattern = await self._extract_pattern(cluster_traces)
            
            if pattern and self._is_pattern_valid(pattern):
                patterns.append(pattern)
        
        logger.info(f"Identified {len(patterns)} valid patterns")
        return patterns
    
    async def _load_traces(
        self,
        days: int,
        limit: int
    ) -> List[TaskExecutionTrace]:
        """加载执行轨迹"""
        traces = []
        
        # 从轨迹存储目录加载
        trace_files = list(self.traces_dir.glob("*.json"))[:limit]
        
        cutoff_time = datetime.now() - timedelta(days=days)
        
        for trace_file in trace_files:
            try:
                with open(trace_file, "r", encoding="utf-8") as f:
                    trace_data = json.load(f)
                
                created_at_str = trace_data.get("created_at", "")
                if created_at_str:
                    created_at = datetime.fromisoformat(created_at_str)
                    if created_at >= cutoff_time:
                        trace = self._convert_trace(trace_data)
                        traces.append(trace)
            except Exception as e:
                logger.warning(f"Failed to load trace {trace_file}: {e}")
        
        return traces
    
    def _convert_trace(self, trace_data: Dict) -> TaskExecutionTrace:
        """将原始轨迹数据转换为TaskExecutionTrace"""
        # 解析任务类型
        task_type_str = trace_data.get("task_type", "unknown")
        try:
            task_type = TaskType(task_type_str)
        except ValueError:
            task_type = TaskType.UNKNOWN
        
        # 解析执行状态
        status_str = trace_data.get("status", "failed")
        try:
            status = ExecutionStatus.SUCCESS if status_str == "completed" else ExecutionStatus.FAILED
        except ValueError:
            status = ExecutionStatus.FAILED
        
        # 解析时间戳
        created_at_str = trace_data.get("created_at", "")
        try:
            created_at = datetime.fromisoformat(created_at_str)
        except:
            created_at = datetime.now()
        
        # 提取user_request（从query字段）
        user_request = trace_data.get("query", "")
        
        # 提取tools_called
        tools_called = trace_data.get("tool_calls", [])
        
        return TaskExecutionTrace(
            trace_id=trace_data.get("trace_id", ""),
            conversation_id=trace_data.get("conversation_id", ""),
            user_request=user_request,
            task_type=task_type,
            intent_classification=trace_data.get("intent_classification"),
            intent_confidence=trace_data.get("intent_confidence", 0.0),
            routed_nodes=trace_data.get("routed_nodes", []),
            tools_called=tools_called,
            skills_activated=trace_data.get("skills_activated", []),
            execution_steps=trace_data.get("events", []),
            status=status,
            response=trace_data.get("response", ""),
            user_feedback=trace_data.get("user_feedback"),
            total_duration_ms=trace_data.get("total_duration_ms", 0.0),
            token_usage=trace_data.get("token_usage", {}),
            created_at=created_at,
            metadata=trace_data.get("metadata", {}),
        )
    
    async def _embed_traces(
        self,
        traces: List[TaskExecutionTrace]
    ) -> np.ndarray:
        """向量化任务描述"""
        texts = []
        for t in traces:
            # 组合任务描述
            tools_str = " ".join([tool.get("name", "") for tool in t.tools_called])
            text = f"{t.user_request} {t.intent_classification or ''} {tools_str}"
            texts.append(text)
        
        # 如果有向量存储，使用它进行向量化
        if self.vector_store:
            embeddings = []
            for text in texts:
                embedding = await self.vector_store.embed(text)
                embeddings.append(embedding)
            return np.array(embeddings)
        else:
            # 简化实现：使用TF-IDF向量化
            from sklearn.feature_extraction.text import TfidfVectorizer
            vectorizer = TfidfVectorizer(max_features=100)
            embeddings = vectorizer.fit_transform(texts).toarray()
            return embeddings
    
    def _cluster_traces(
        self,
        similarity_matrix: np.ndarray
    ) -> List[List[int]]:
        """
        聚类相似任务
        
        使用DBSCAN算法进行聚类
        """
        # 转换为距离矩阵
        distance_matrix = 1 - similarity_matrix
        
        # DBSCAN聚类
        clustering = DBSCAN(
            eps=1 - self.similarity_threshold,
            min_samples=self.min_frequency,
            metric="precomputed"
        )
        
        labels = clustering.fit_predict(distance_matrix)
        
        # 按聚类标签分组
        clusters = {}
        for idx, label in enumerate(labels):
            if label == -1:  # 噪声点
                continue
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(idx)
        
        return list(clusters.values())
    
    async def _extract_pattern(
        self,
        traces: List[TaskExecutionTrace]
    ) -> Optional[SkillPattern]:
        """从一组相似任务中提取模式"""
        if not traces:
            return None
        
        # 统计共同特征
        common_intent = self._find_common_intent(traces)
        common_tools = self._find_common_tools(traces)
        common_workflow = self._extract_common_workflow(traces)
        
        # 计算统计指标
        success_count = sum(1 for t in traces if t.status == ExecutionStatus.SUCCESS)
        success_rate = success_count / len(traces)
        
        avg_duration = sum(t.total_duration_ms for t in traces) / len(traces)
        
        # 生成模式描述
        description = self._generate_pattern_description(
            traces, common_intent, common_tools, common_workflow
        )
        
        pattern = SkillPattern(
            pattern_id=f"pattern_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            pattern_name=self._generate_pattern_name(common_intent, common_tools),
            description=description,
            similar_tasks=[t.trace_id for t in traces],
            task_count=len(traces),
            common_intent=common_intent,
            common_tools=common_tools,
            common_workflow=common_workflow,
            frequency=len(traces),
            success_rate=success_rate,
            avg_duration_ms=avg_duration,
            evolution_score=self._calculate_evolution_score(
                len(traces), success_rate, avg_duration
            ),
            first_seen=min(t.created_at for t in traces),
            last_seen=max(t.created_at for t in traces),
        )
        
        return pattern
    
    def _find_common_intent(self, traces: List[TaskExecutionTrace]) -> str:
        """找出最常见的意图"""
        intent_counts = {}
        for trace in traces:
            intent = trace.intent_classification or "unknown"
            intent_counts[intent] = intent_counts.get(intent, 0) + 1
        
        return max(intent_counts, key=intent_counts.get) if intent_counts else "unknown"
    
    def _find_common_tools(self, traces: List[TaskExecutionTrace]) -> List[str]:
        """找出共同使用的工具"""
        tool_counts = {}
        for trace in traces:
            for tool in trace.tools_called:
                tool_name = tool.get("name", "")
                if tool_name:
                    tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
        
        # 返回在超过50%任务中出现的工具
        threshold = len(traces) * 0.5
        return [tool for tool, count in tool_counts.items() if count >= threshold]
    
    def _extract_common_workflow(self, traces: List[TaskExecutionTrace]) -> List[str]:
        """提取共同工作流步骤"""
        # 提取工具调用序列的共同部分
        all_sequences = [
            [tool.get("name", "") for tool in trace.tools_called if tool.get("name")]
            for trace in traces
        ]
        
        # 找出最长公共子序列
        if not all_sequences:
            return []
        
        common_seq = all_sequences[0]
        for seq in all_sequences[1:]:
            common_seq = self._longest_common_subsequence(common_seq, seq)
        
        return common_seq
    
    def _longest_common_subsequence(self, seq1: List[str], seq2: List[str]) -> List[str]:
        """最长公共子序列算法"""
        m, n = len(seq1), len(seq2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if seq1[i-1] == seq2[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])
        
        # 回溯找出LCS
        lcs = []
        i, j = m, n
        while i > 0 and j > 0:
            if seq1[i-1] == seq2[j-1]:
                lcs.append(seq1[i-1])
                i -= 1
                j -= 1
            elif dp[i-1][j] > dp[i][j-1]:
                i -= 1
            else:
                j -= 1
        
        return lcs[::-1]
    
    def _calculate_evolution_score(
        self,
        frequency: int,
        success_rate: float,
        avg_duration: float
    ) -> float:
        """
        计算模式固化价值评分
        
        考虑因素：
        1. 频率（越高越好）
        2. 成功率（越高越好）
        3. 执行时间（越长说明越复杂，固化价值越高）
        """
        # 归一化
        freq_score = min(frequency / 10, 1.0)  # 10次以上为满分
        success_score = success_rate
        duration_score = min(avg_duration / 10000, 1.0)  # 10秒以上为满分
        
        # 加权平均
        return 0.4 * freq_score + 0.4 * success_score + 0.2 * duration_score
    
    def _is_pattern_valid(self, pattern: SkillPattern) -> bool:
        """验证模式是否值得固化"""
        return (
            pattern.frequency >= self.min_frequency and
            pattern.success_rate >= self.min_success_rate and
            pattern.evolution_score >= 0.5
        )
    
    def _generate_pattern_description(
        self,
        traces: List[TaskExecutionTrace],
        common_intent: str,
        common_tools: List[str],
        common_workflow: List[str]
    ) -> str:
        """生成模式描述"""
        examples = [t.user_request for t in traces[:3]]
        
        description = f"""检测到重复任务模式：
- 意图类型：{common_intent}
- 常用工具：{', '.join(common_tools)}
- 典型工作流：{' → '.join(common_workflow)}
- 出现频率：{len(traces)}次
- 成功率：{sum(1 for t in traces if t.status == ExecutionStatus.SUCCESS) / len(traces):.1%}

示例请求：
{chr(10).join(f'{i+1}. {ex}' for i, ex in enumerate(examples))}"""
        
        return description.strip()
    
    def _generate_pattern_name(
        self,
        common_intent: str,
        common_tools: List[str]
    ) -> str:
        """生成模式名称"""
        if common_tools:
            return f"{common_intent}_with_{'_'.join(common_tools[:2])}"
        return common_intent

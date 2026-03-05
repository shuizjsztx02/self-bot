"""
自进化系统数据模型

定义所有核心数据结构，用于模式识别、工作流提取和Skill生成
"""
from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class TaskType(str, Enum):
    """任务类型枚举"""
    RAG_QUERY = "rag_query"
    WEB_SEARCH = "web_search"
    DOCUMENT_PROCESSING = "document_processing"
    CODE_GENERATION = "code_generation"
    DATA_ANALYSIS = "data_analysis"
    GENERAL_CHAT = "general_chat"
    SKILL_EXECUTION = "skill_execution"
    UNKNOWN = "unknown"


class ExecutionStatus(str, Enum):
    """执行状态枚举"""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


class TaskExecutionTrace(BaseModel):
    """
    任务执行轨迹
    
    记录完整的任务执行过程，用于模式识别分析
    """
    trace_id: str
    conversation_id: str
    user_request: str
    task_type: TaskType = TaskType.UNKNOWN
    
    # 意图识别
    intent_classification: Optional[str] = None
    intent_confidence: float = 0.0
    routed_nodes: List[str] = Field(default_factory=list)
    
    # 执行过程
    tools_called: List[Dict[str, Any]] = Field(default_factory=list)
    skills_activated: List[str] = Field(default_factory=list)
    execution_steps: List[Dict[str, Any]] = Field(default_factory=list)
    
    # 结果
    status: ExecutionStatus = ExecutionStatus.FAILED
    response: str = ""
    user_feedback: Optional[str] = None
    
    # 性能指标
    total_duration_ms: float = 0.0
    token_usage: Dict[str, int] = Field(default_factory=dict)
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SkillPattern(BaseModel):
    """
    识别的Skill模式
    
    从任务执行轨迹中识别出的可复用模式
    """
    pattern_id: str
    pattern_name: str
    description: str
    
    # 相似任务聚类
    similar_tasks: List[str] = Field(default_factory=list)  # trace_id列表
    task_count: int = 0
    
    # 共同特征
    common_intent: str = ""
    common_tools: List[str] = Field(default_factory=list)
    common_workflow: List[str] = Field(default_factory=list)
    
    # 统计指标
    frequency: int = 0  # 出现频率
    success_rate: float = 0.0  # 成功率
    avg_duration_ms: float = 0.0  # 平均执行时间
    user_satisfaction: Optional[float] = None  # 用户满意度
    
    # 固化价值评分
    evolution_score: float = Field(default=0.0)
    
    # 时间戳
    first_seen: datetime = Field(default_factory=datetime.now)
    last_seen: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WorkflowDefinition(BaseModel):
    """
    工作流定义
    
    从多个相似任务中提取的标准化工作流程
    """
    workflow_id: str
    name: str
    description: str
    
    # 步骤序列
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    
    # 参数化部分
    parameters: List[Dict[str, Any]] = Field(default_factory=list)
    
    # 条件分支
    branches: Optional[Dict[str, Any]] = None
    
    # 示例
    examples: List[Dict[str, Any]] = Field(default_factory=list)
    
    # 元数据
    source_pattern_id: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class GeneratedSkill(BaseModel):
    """
    生成的Skill
    
    自动生成的Skill对象，包含SKILL.md内容和元数据
    """
    skill_id: str
    name: str
    description: str
    
    # SKILL.md内容
    skill_md_content: str = ""
    
    # 辅助资源
    scripts: List[Dict[str, str]] = Field(default_factory=list)
    references: List[Dict[str, str]] = Field(default_factory=list)
    
    # 来源
    source_pattern: Optional[SkillPattern] = None
    source_workflow: Optional[WorkflowDefinition] = None
    
    # 验证结果
    validation_score: float = 0.0
    validation_issues: List[str] = Field(default_factory=list)
    
    # 状态
    status: str = "draft"  # draft, validated, registered, deprecated
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    registered_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class EvolutionMetrics(BaseModel):
    """
    自进化指标
    
    跟踪自进化系统的整体性能和统计信息
    """
    # 计数指标
    total_patterns_detected: int = 0
    skills_generated: int = 0
    skills_registered: int = 0
    skills_in_use: int = 0
    
    # 质量指标
    avg_skill_quality_score: float = 0.0
    avg_user_satisfaction: float = 0.0
    
    # 时间指标
    last_analysis_time: Optional[datetime] = None
    next_scheduled_analysis: Optional[datetime] = None
    
    # 性能指标
    total_traces_analyzed: int = 0
    avg_analysis_duration_ms: float = 0.0
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class ValidationResult(BaseModel):
    """
    Skill验证结果
    
    包含验证状态、评分和问题列表
    """
    is_valid: bool = False
    score: float = 0.0
    issues: List[str] = Field(default_factory=list)
    
    # 详细评分
    format_score: float = 0.0
    content_score: float = 0.0
    quality_score: float = 0.0
    
    class Config:
        pass

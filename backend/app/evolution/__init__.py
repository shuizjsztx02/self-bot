"""
自进化系统模块

提供自动识别任务模式、生成Skill和持续进化的能力
"""
from .config import evolution_settings, EvolutionSettings
from .models import (
    TaskExecutionTrace,
    SkillPattern,
    WorkflowDefinition,
    GeneratedSkill,
    EvolutionMetrics,
    ValidationResult,
    TaskType,
    ExecutionStatus,
)
from .pattern_recognizer import PatternRecognizer
from .workflow_extractor import WorkflowExtractor
from .skill_generator import SkillGenerator
from .skill_validator import SkillValidator
from .evolution_monitor import EvolutionMonitor, get_evolution_monitor

__all__ = [
    # 配置
    "evolution_settings",
    "EvolutionSettings",
    
    # 数据模型
    "TaskExecutionTrace",
    "SkillPattern",
    "WorkflowDefinition",
    "GeneratedSkill",
    "EvolutionMetrics",
    "ValidationResult",
    "TaskType",
    "ExecutionStatus",
    
    # 核心组件
    "PatternRecognizer",
    "WorkflowExtractor",
    "SkillGenerator",
    "SkillValidator",
    "EvolutionMonitor",
    "get_evolution_monitor",
]

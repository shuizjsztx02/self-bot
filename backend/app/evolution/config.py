"""
自进化系统配置
"""
from pydantic_settings import BaseSettings


class EvolutionSettings(BaseSettings):
    """自进化配置"""
    
    # 开关
    EVOLUTION_ENABLED: bool = True
    
    # 模式识别
    PATTERN_MIN_FREQUENCY: int = 3
    PATTERN_MIN_SUCCESS_RATE: float = 0.8
    PATTERN_SIMILARITY_THRESHOLD: float = 0.75
    
    # 监控
    EVOLUTION_CHECK_INTERVAL_HOURS: int = 1
    EVOLUTION_ANALYSIS_DAYS: int = 7
    EVOLUTION_MIN_TRACES: int = 10
    
    # Skill生成
    SKILL_AUTO_REGISTER: bool = True
    SKILL_OUTPUT_DIR: str = "./skills/evolved"
    SKILL_VALIDATION_THRESHOLD: float = 0.7
    
    # 存储
    EVOLUTION_DATA_DIR: str = "./data/evolution"
    
    class Config:
        env_prefix = "EVOLUTION_"


evolution_settings = EvolutionSettings()

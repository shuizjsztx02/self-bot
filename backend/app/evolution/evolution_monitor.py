"""
自进化监控进程

后台定期分析工作历史，自动触发Skill生成和注册
"""
from typing import Optional
import asyncio
import logging
from datetime import datetime, timedelta

from .pattern_recognizer import PatternRecognizer
from .skill_generator import SkillGenerator
from .skill_validator import SkillValidator
from .models import EvolutionMetrics
from .config import evolution_settings

logger = logging.getLogger(__name__)


class EvolutionMonitor:
    """自进化监控进程"""
    
    def __init__(
        self,
        check_interval_hours: int = None,
        min_traces_for_analysis: int = None,
        auto_register: bool = None,
    ):
        self.check_interval_hours = check_interval_hours or evolution_settings.EVOLUTION_CHECK_INTERVAL_HOURS
        self.min_traces_for_analysis = min_traces_for_analysis or evolution_settings.EVOLUTION_MIN_TRACES
        self.auto_register = auto_register if auto_register is not None else evolution_settings.SKILL_AUTO_REGISTER
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        # 初始化组件
        self.pattern_recognizer = PatternRecognizer()
        self.skill_generator = SkillGenerator()
        self.skill_validator = SkillValidator()
        
        self.metrics = EvolutionMetrics()
    
    async def start(self):
        """启动监控进程"""
        if self._running:
            logger.warning("EvolutionMonitor is already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"EvolutionMonitor started, check interval: {self.check_interval_hours}h")
    
    async def stop(self):
        """停止监控进程"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("EvolutionMonitor stopped")
    
    async def _run_loop(self):
        """主循环"""
        while self._running:
            try:
                await self._analyze_and_evolve()
            except Exception as e:
                logger.error(f"Error in evolution loop: {e}", exc_info=True)
            
            # 等待下次检查
            await asyncio.sleep(self.check_interval_hours * 3600)
    
    async def _analyze_and_evolve(self):
        """分析并进化"""
        logger.info("[EvolutionMonitor] Starting analysis cycle")
        
        start_time = datetime.now()
        
        try:
            # 1. 分析最近的执行轨迹
            patterns = await self.pattern_recognizer.analyze_recent_traces(days=7)
            
            if not patterns:
                logger.info("No patterns detected")
                return
            
            self.metrics.total_patterns_detected = len(patterns)
            
            # 2. 为每个有效模式生成Skill
            for pattern in patterns:
                try:
                    skill = await self.skill_generator.generate_skill(pattern)
                    
                    if not skill:
                        continue
                    
                    self.metrics.skills_generated += 1
                    
                    # 3. 验证Skill
                    validation_result = await self.skill_validator.validate(skill)
                    skill.validation_score = validation_result.score
                    skill.validation_issues = validation_result.issues
                    
                    if not validation_result.is_valid:
                        logger.warning(f"Skill validation failed: {validation_result.issues}")
                        continue
                    
                    # 4. 保存Skill
                    await self.skill_generator.save_skill(skill)
                    
                    # 5. 自动注册（如果启用）
                    if self.auto_register:
                        await self._register_skill(skill)
                    
                except Exception as e:
                    logger.error(f"Failed to generate skill for pattern {pattern.pattern_id}: {e}")
            
            # 更新指标
            self.metrics.last_analysis_time = datetime.now()
            self.metrics.next_scheduled_analysis = datetime.now() + timedelta(hours=self.check_interval_hours)
            
            duration = (datetime.now() - start_time).total_seconds() * 1000
            self.metrics.avg_analysis_duration_ms = duration
            
            logger.info(f"[EvolutionMonitor] Analysis cycle completed: {self.metrics.skills_generated} skills generated")
            
        except Exception as e:
            logger.error(f"Error in analysis cycle: {e}", exc_info=True)
    
    async def _register_skill(self, skill):
        """
        注册Skill到系统
        
        实施分级注册策略
        """
        try:
            # 计算信任度
            trust_score = self._calculate_trust_score(skill)
            
            if trust_score >= 0.9:
                # 高信任度：自动激活
                skill.status = "active"
                logger.info(f"Skill activated (high trust): {skill.name}")
                self.metrics.skills_registered += 1
                self.metrics.skills_in_use += 1
                
            elif trust_score >= 0.7:
                # 中信任度：待审核
                skill.status = "pending_review"
                logger.info(f"Skill pending review (medium trust): {skill.name}")
                self.metrics.skills_registered += 1
                
                # TODO: 发送通知给管理员
                
            else:
                # 低信任度：仅保存
                skill.status = "draft"
                logger.info(f"Skill saved as draft (low trust): {skill.name}")
                
        except Exception as e:
            logger.error(f"Error registering skill: {e}")
    
    def _calculate_trust_score(self, skill) -> float:
        """
        计算Skill信任度
        
        基于源模式质量、验证结果等
        """
        score = 0.0
        
        # 基于源模式质量
        if skill.source_pattern:
            score += skill.source_pattern.success_rate * 0.3
            score += min(skill.source_pattern.frequency / 10, 1.0) * 0.2
        
        # 基于验证结果
        score += skill.validation_score * 0.5
        
        return min(score, 1.0)
    
    def get_metrics(self) -> EvolutionMetrics:
        """获取进化指标"""
        return self.metrics


# 全局单例
_evolution_monitor: Optional[EvolutionMonitor] = None


def get_evolution_monitor() -> EvolutionMonitor:
    """获取进化监控实例"""
    global _evolution_monitor
    if _evolution_monitor is None:
        _evolution_monitor = EvolutionMonitor()
    return _evolution_monitor

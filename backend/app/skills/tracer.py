"""
Skills 追踪模块
追踪 skills 的加载、匹配、激活和 prompt 注入过程
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class SkillTraceStep:
    """单个追踪步骤"""
    step_name: str
    step_type: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "step_name": self.step_name,
            "step_type": self.step_type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


class SkillTracer:
    """Skills 追踪器"""
    
    def __init__(self):
        self._steps: List[SkillTraceStep] = []
        self._enabled: bool = True
        self._max_steps: int = 100
    
    def enable(self):
        """启用追踪"""
        self._enabled = True
    
    def disable(self):
        """禁用追踪"""
        self._enabled = False
    
    def clear(self):
        """清空追踪记录"""
        self._steps.clear()
    
    def trace(
        self,
        step_name: str,
        step_type: str,
        data: Dict[str, Any],
    ):
        """
        记录追踪步骤
        
        Args:
            step_name: 步骤名称
            step_type: 步骤类型 (loader, matcher, manager, prompt, tool)
            data: 追踪数据
        """
        if not self._enabled:
            return
        
        step = SkillTraceStep(
            step_name=step_name,
            step_type=step_type,
            data=data,
        )
        
        self._steps.append(step)
        
        if len(self._steps) > self._max_steps:
            self._steps = self._steps[-self._max_steps:]
        
        self._log_step(step)
    
    def _log_step(self, step: SkillTraceStep):
        """输出日志"""
        data_str = json.dumps(step.data, ensure_ascii=False, default=str)
        if len(data_str) > 200:
            data_str = data_str[:200] + "..."
        
        logger.info(f"[Skill:{step.step_type.upper()}] {step.step_name} | {data_str}")
    
    def get_steps(self) -> List[Dict]:
        """获取所有追踪步骤"""
        return [step.to_dict() for step in self._steps]
    
    def get_steps_by_type(self, step_type: str) -> List[Dict]:
        """按类型获取追踪步骤"""
        return [
            step.to_dict() 
            for step in self._steps 
            if step.step_type == step_type
        ]
    
    def get_report(self) -> str:
        """生成追踪报告"""
        if not self._steps:
            return "No skill trace steps recorded."
        
        lines = ["=" * 60, "Skills Trace Report", "=" * 60]
        
        current_type = None
        for step in self._steps:
            if step.step_type != current_type:
                current_type = step.step_type
                lines.append(f"\n[{current_type.upper()}]")
            
            data_str = json.dumps(step.data, ensure_ascii=False, default=str)
            if len(data_str) > 100:
                data_str = data_str[:100] + "..."
            
            lines.append(f"  {step.step_name}: {data_str}")
        
        lines.append("\n" + "=" * 60)
        return "\n".join(lines)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        type_counts = {}
        for step in self._steps:
            type_counts[step.step_type] = type_counts.get(step.step_type, 0) + 1
        
        return {
            "total_steps": len(self._steps),
            "by_type": type_counts,
            "enabled": self._enabled,
        }


_skill_tracer = SkillTracer()


def get_skill_tracer() -> SkillTracer:
    """获取全局 SkillTracer 实例"""
    return _skill_tracer


def skill_trace_step(step_name: str, step_type: str, data: Dict[str, Any]):
    """
    追踪装饰器/上下文管理器
    
    用法:
        with skill_trace_step("match", "matcher", {"query": query}):
            # ... 代码 ...
    """
    return SkillTraceContext(step_name, step_type, data)


class SkillTraceContext:
    """追踪上下文管理器"""
    
    def __init__(
        self,
        step_name: str,
        step_type: str,
        data: Dict[str, Any],
    ):
        self.step_name = step_name
        self.step_type = step_type
        self.data = data
        self._start_time = None
    
    def __enter__(self):
        self._start_time = datetime.now()
        self.data["_start_time"] = self._start_time.isoformat()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = datetime.now()
        self.data["_end_time"] = end_time.isoformat()
        
        if self._start_time:
            duration = (end_time - self._start_time).total_seconds()
            self.data["_duration_ms"] = round(duration * 1000, 2)
        
        if exc_type:
            self.data["_error"] = str(exc_val)
        
        _skill_tracer.trace(self.step_name, self.step_type, self.data)
        return False

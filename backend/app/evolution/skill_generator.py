"""
Skill自动生成器

从识别的模式自动生成SKILL.md文件
"""
from typing import Optional, Dict, Any
from datetime import datetime
import logging
from pathlib import Path

from .models import SkillPattern, WorkflowDefinition, GeneratedSkill
from .workflow_extractor import WorkflowExtractor
from .config import evolution_settings

logger = logging.getLogger(__name__)


class SkillGenerator:
    """Skill自动生成器"""
    
    def __init__(
        self,
        llm=None,
        skills_output_dir: str = None,
        prompt_template_path: str = None,
    ):
        self.llm = llm
        self.skills_output_dir = Path(skills_output_dir or evolution_settings.SKILL_OUTPUT_DIR)
        self.prompt_template_path = Path(prompt_template_path or "prompts/evolution/skill_generation.md")
        self.workflow_extractor = WorkflowExtractor()
        
        # 确保输出目录存在
        self.skills_output_dir.mkdir(parents=True, exist_ok=True)
    
    async def generate_skill(
        self,
        pattern: SkillPattern
    ) -> Optional[GeneratedSkill]:
        """
        从识别的模式生成Skill
        
        Args:
            pattern: 识别的任务模式
            
        Returns:
            生成的Skill对象
        """
        logger.info(f"[SkillGenerator] Generating skill for pattern: {pattern.pattern_name}")
        
        # 1. 提取工作流
        workflow = await self.workflow_extractor.extract_workflow(pattern)
        if not workflow:
            logger.warning("Failed to extract workflow")
            return None
        
        # 2. 生成Skill名称和描述
        skill_name = self._generate_skill_name(pattern)
        skill_description = self._generate_skill_description(pattern, workflow)
        
        # 3. 生成SKILL.md内容
        skill_md_content = await self._generate_skill_md(
            skill_name, skill_description, pattern, workflow
        )
        
        # 4. 创建GeneratedSkill对象
        skill = GeneratedSkill(
            skill_id=f"skill_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            name=skill_name,
            description=skill_description,
            skill_md_content=skill_md_content,
            source_pattern=pattern,
            source_workflow=workflow,
        )
        
        return skill
    
    def _generate_skill_name(self, pattern: SkillPattern) -> str:
        """生成Skill名称（kebab-case）"""
        # 转换为kebab-case
        name = pattern.pattern_name.lower().replace(" ", "-").replace("_", "-")
        
        # 移除特殊字符
        name = ''.join(c for c in name if c.isalnum() or c == '-')
        
        # 限制长度
        return name[:64]
    
    def _generate_skill_description(
        self,
        pattern: SkillPattern,
        workflow: WorkflowDefinition
    ) -> str:
        """生成Skill描述"""
        # 基于模式信息生成描述
        description = f"自动生成的Skill，用于处理{pattern.common_intent}类型的任务。"
        
        if pattern.common_tools:
            tools_str = "、".join(pattern.common_tools[:3])
            description += f" 主要使用{tools_str}等工具。"
        
        description += f" 基于{pattern.frequency}次成功执行总结，成功率{pattern.success_rate:.1%}。"
        
        return description[:200]  # 限制长度
    
    async def _generate_skill_md(
        self,
        skill_name: str,
        description: str,
        pattern: SkillPattern,
        workflow: WorkflowDefinition
    ) -> str:
        """生成SKILL.md完整内容"""
        
        # 生成工作流步骤说明
        workflow_steps_md = self._format_workflow_steps(workflow)
        
        # 生成参数说明
        parameters_md = self._format_parameters(workflow)
        
        # 生成示例
        examples_md = self._format_examples(pattern)
        
        # 组装SKILL.md
        skill_md = f"""---
name: {skill_name}
description: {description}
version: 1.0.0
tags: [auto-generated, {pattern.common_intent}]
generated_at: {datetime.now().isoformat()}
source_pattern: {pattern.pattern_id}
---

# {skill_name.replace('-', ' ').title()}

## 概述

{description}

此Skill通过分析{pattern.frequency}次成功执行的任务自动生成，成功率为{pattern.success_rate:.1%}。

## 使用场景

{self._generate_usage_scenarios(pattern)}

## 工作流程

{workflow_steps_md}

## 参数说明

{parameters_md}

## 示例

{examples_md}

## 注意事项

{self._generate_best_practices(pattern, workflow)}

## 元数据

- 自动生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 源模式ID：{pattern.pattern_id}
- 原始任务数：{pattern.task_count}
- 平均执行时间：{pattern.avg_duration_ms:.0f}ms
"""
        
        return skill_md.strip()
    
    def _format_workflow_steps(self, workflow: WorkflowDefinition) -> str:
        """格式化工作流步骤"""
        if not workflow.steps:
            return "暂无详细步骤"
        
        steps_md = []
        for i, step in enumerate(workflow.steps, 1):
            step_name = step.get("name", f"步骤{i}")
            step_desc = step.get("description", "")
            steps_md.append(f"{i}. **{step_name}**")
            if step_desc:
                steps_md.append(f"   {step_desc}")
        
        return "\n".join(steps_md)
    
    def _format_parameters(self, workflow: WorkflowDefinition) -> str:
        """格式化参数说明"""
        if not workflow.parameters:
            return "此Skill无需额外参数"
        
        params_md = []
        for param in workflow.parameters:
            param_name = param.get("name", "未知参数")
            param_type = param.get("type", "string")
            param_desc = param.get("description", "")
            param_required = param.get("required", False)
            
            params_md.append(
                f"- `{param_name}` ({param_type}, {'必需' if param_required else '可选'}): {param_desc}"
            )
        
        return "\n".join(params_md)
    
    def _format_examples(self, pattern: SkillPattern) -> str:
        """格式化示例"""
        examples_md = []
        
        # 从相似任务中提取示例
        examples_md.append(f"**典型请求示例：**")
        examples_md.append(f"- 意图类型：{pattern.common_intent}")
        examples_md.append(f"- 常用工具：{', '.join(pattern.common_tools)}")
        examples_md.append(f"- 成功执行{pattern.frequency}次")
        
        return "\n".join(examples_md)
    
    def _generate_usage_scenarios(self, pattern: SkillPattern) -> str:
        """生成使用场景说明"""
        scenarios = [
            f"- 当用户请求涉及{pattern.common_intent}时自动触发",
            f"- 适用于需要使用{', '.join(pattern.common_tools[:3])}的任务",
            f"- 历史数据显示此类任务出现频率较高（{pattern.frequency}次）",
        ]
        return "\n".join(scenarios)
    
    def _generate_best_practices(
        self,
        pattern: SkillPattern,
        workflow: WorkflowDefinition
    ) -> str:
        """生成最佳实践建议"""
        practices = [
            "- 确保相关工具可用且配置正确",
            f"- 此Skill基于{pattern.frequency}次成功执行总结，建议在实际使用中继续优化",
        ]
        
        if pattern.success_rate < 0.95:
            practices.append(f"- 当前成功率{pattern.success_rate:.1%}，可能需要人工审核关键步骤")
        
        return "\n".join(practices)
    
    async def save_skill(self, skill: GeneratedSkill) -> bool:
        """
        保存生成的Skill到文件系统
        
        Args:
            skill: 生成的Skill对象
            
        Returns:
            是否保存成功
        """
        try:
            skill_dir = self.skills_output_dir / skill.name
            skill_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存SKILL.md
            skill_md_path = skill_dir / "SKILL.md"
            skill_md_path.write_text(skill.skill_md_content, encoding="utf-8")
            
            # 保存元数据
            metadata = {
                "skill_id": skill.skill_id,
                "name": skill.name,
                "description": skill.description,
                "created_at": skill.created_at.isoformat(),
                "status": skill.status,
            }
            
            if skill.source_pattern:
                pattern_dict = skill.source_pattern.model_dump()
                # 转换datetime对象为字符串
                if 'created_at' in pattern_dict and pattern_dict['created_at']:
                    pattern_dict['created_at'] = pattern_dict['created_at'].isoformat()
                if 'first_seen' in pattern_dict and pattern_dict['first_seen']:
                    pattern_dict['first_seen'] = pattern_dict['first_seen'].isoformat()
                if 'last_seen' in pattern_dict and pattern_dict['last_seen']:
                    pattern_dict['last_seen'] = pattern_dict['last_seen'].isoformat()
                metadata["source_pattern"] = pattern_dict
            
            import json
            metadata_path = skill_dir / "metadata.json"
            metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            
            logger.info(f"Skill saved to {skill_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save skill: {e}")
            return False

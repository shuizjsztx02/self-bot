"""
工作流提取器

从多个相似任务中提取标准化工作流程
"""
from typing import List, Optional, Dict, Any
import logging
from collections import Counter

from .models import SkillPattern, WorkflowDefinition

logger = logging.getLogger(__name__)


class WorkflowExtractor:
    """工作流提取器"""
    
    async def extract_workflow(
        self,
        pattern: SkillPattern
    ) -> Optional[WorkflowDefinition]:
        """
        从模式中提取工作流定义
        
        Args:
            pattern: 识别的任务模式
            
        Returns:
            工作流定义对象
        """
        logger.info(f"[WorkflowExtractor] Extracting workflow for pattern: {pattern.pattern_name}")
        
        # 1. 提取步骤序列
        steps = self._extract_steps(pattern)
        
        # 2. 识别参数
        parameters = self._identify_parameters(pattern)
        
        # 3. 提取示例
        examples = self._extract_examples(pattern)
        
        # 4. 创建工作流定义
        workflow = WorkflowDefinition(
            workflow_id=f"workflow_{pattern.pattern_id}",
            name=pattern.pattern_name,
            description=pattern.description,
            steps=steps,
            parameters=parameters,
            examples=examples,
            source_pattern_id=pattern.pattern_id,
        )
        
        logger.info(f"[WorkflowExtractor] Workflow extracted with {len(steps)} steps")
        return workflow
    
    def _extract_steps(self, pattern: SkillPattern) -> List[Dict[str, Any]]:
        """
        提取工作流步骤
        
        基于共同工作流生成步骤序列
        """
        steps = []
        
        # 基于共同工作流生成步骤
        for i, tool_name in enumerate(pattern.common_workflow):
            step = {
                "name": f"step_{i+1}_{tool_name}",
                "tool": tool_name,
                "description": f"调用{tool_name}工具",
                "order": i + 1,
            }
            steps.append(step)
        
        # 如果没有共同工作流，基于工具列表生成
        if not steps and pattern.common_tools:
            for i, tool_name in enumerate(pattern.common_tools):
                step = {
                    "name": f"step_{i+1}_{tool_name}",
                    "tool": tool_name,
                    "description": f"调用{tool_name}工具",
                    "order": i + 1,
                }
                steps.append(step)
        
        return steps
    
    def _identify_parameters(self, pattern: SkillPattern) -> List[Dict[str, Any]]:
        """
        识别可参数化的部分
        
        基于意图类型推断可能的参数
        """
        parameters = []
        
        # 基于意图类型推断参数
        intent_lower = pattern.common_intent.lower()
        
        if "query" in intent_lower or "search" in intent_lower:
            parameters.append({
                "name": "query",
                "type": "string",
                "description": "用户查询内容",
                "required": True,
            })
        
        if "document" in intent_lower:
            parameters.append({
                "name": "document_path",
                "type": "string",
                "description": "文档路径",
                "required": True,
            })
        
        if "code" in intent_lower:
            parameters.append({
                "name": "code_snippet",
                "type": "string",
                "description": "代码片段",
                "required": False,
            })
        
        if "data" in intent_lower or "analysis" in intent_lower:
            parameters.append({
                "name": "data_source",
                "type": "string",
                "description": "数据源路径或URL",
                "required": True,
            })
        
        return parameters
    
    def _extract_examples(self, pattern: SkillPattern) -> List[Dict[str, Any]]:
        """
        提取示例
        
        生成示例模板
        """
        examples = []
        
        # 生成示例模板
        example = {
            "input": f"用户请求涉及{pattern.common_intent}",
            "workflow": [step["name"] for step in self._extract_steps(pattern)],
            "output": "成功完成任务",
        }
        examples.append(example)
        
        return examples
    
    def merge_workflows(
        self,
        workflow1: WorkflowDefinition,
        workflow2: WorkflowDefinition
    ) -> WorkflowDefinition:
        """
        合并两个工作流
        
        用于Skill去重和优化
        """
        # 合并步骤（去重）
        steps_map = {}
        for step in workflow1.steps + workflow2.steps:
            step_name = step.get("name", "")
            if step_name not in steps_map:
                steps_map[step_name] = step
        
        merged_steps = sorted(steps_map.values(), key=lambda x: x.get("order", 0))
        
        # 合并参数
        params_map = {}
        for param in workflow1.parameters + workflow2.parameters:
            param_name = param.get("name", "")
            if param_name not in params_map:
                params_map[param_name] = param
        
        merged_params = list(params_map.values())
        
        # 合并示例
        merged_examples = workflow1.examples + workflow2.examples
        
        # 创建合并后的工作流
        return WorkflowDefinition(
            workflow_id=f"merged_{workflow1.workflow_id}_{workflow2.workflow_id}",
            name=f"Merged: {workflow1.name}",
            description=f"合并工作流: {workflow1.description}",
            steps=merged_steps,
            parameters=merged_params,
            examples=merged_examples[:5],  # 限制示例数量
            source_pattern_id=workflow1.source_pattern_id,
        )

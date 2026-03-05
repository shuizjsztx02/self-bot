"""
Skill验证器

验证生成的Skill质量，包括格式、内容和质量检查
"""
from typing import List, Tuple
import re
import logging

from .models import GeneratedSkill, ValidationResult

logger = logging.getLogger(__name__)


class SkillValidator:
    """Skill验证器"""
    
    async def validate(self, skill: GeneratedSkill) -> ValidationResult:
        """
        验证生成的Skill
        
        Args:
            skill: 待验证的Skill
            
        Returns:
            验证结果
        """
        issues = []
        format_score = 0.0
        content_score = 0.0
        quality_score = 0.0
        
        # 1. 格式验证 (30%权重)
        format_score, format_issues = self._validate_format(skill)
        issues.extend(format_issues)
        
        # 2. 内容验证 (40%权重)
        content_score, content_issues = await self._validate_content(skill)
        issues.extend(content_issues)
        
        # 3. 质量验证 (30%权重)
        quality_score, quality_issues = self._validate_quality(skill)
        issues.extend(quality_issues)
        
        # 计算总分
        total_score = (
            format_score * 0.3 +
            content_score * 0.4 +
            quality_score * 0.3
        )
        
        # 判断是否有效（没有ERROR级别的问题）
        is_valid = len([i for i in issues if i.startswith("ERROR")]) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            score=total_score,
            issues=issues,
            format_score=format_score,
            content_score=content_score,
            quality_score=quality_score,
        )
    
    def _validate_format(self, skill: GeneratedSkill) -> Tuple[float, List[str]]:
        """
        验证格式
        
        检查YAML frontmatter和Markdown结构
        """
        issues = []
        score = 1.0
        
        # 检查YAML frontmatter
        if not skill.skill_md_content.startswith("---"):
            issues.append("ERROR: Missing YAML frontmatter")
            score -= 0.5
        
        # 提取frontmatter
        match = re.match(r'^---\n(.*?)\n---', skill.skill_md_content, re.DOTALL)
        if not match:
            issues.append("ERROR: Invalid frontmatter format")
            score -= 0.5
        else:
            try:
                import yaml
                frontmatter = yaml.safe_load(match.group(1))
                
                # 检查必需字段
                if 'name' not in frontmatter:
                    issues.append("ERROR: Missing 'name' in frontmatter")
                    score -= 0.3
                
                if 'description' not in frontmatter:
                    issues.append("ERROR: Missing 'description' in frontmatter")
                    score -= 0.3
                
            except Exception as e:
                issues.append(f"ERROR: Invalid YAML: {e}")
                score -= 0.5
        
        # 检查名称格式
        if not re.match(r'^[a-z0-9-]+$', skill.name):
            issues.append("WARNING: Name should be kebab-case (lowercase letters, numbers, and hyphens)")
            score -= 0.1
        
        return max(score, 0), issues
    
    async def _validate_content(self, skill: GeneratedSkill) -> Tuple[float, List[str]]:
        """
        验证内容
        
        检查描述完整性、工作流清晰度等
        """
        issues = []
        score = 1.0
        
        # 检查描述长度
        if len(skill.description) < 20:
            issues.append("WARNING: Description too short (should be at least 20 characters)")
            score -= 0.2
        elif len(skill.description) > 500:
            issues.append("WARNING: Description too long (should be less than 500 characters)")
            score -= 0.1
        
        # 检查是否有工作流步骤
        if "## 工作流程" not in skill.skill_md_content and "## Workflow" not in skill.skill_md_content:
            issues.append("WARNING: Missing workflow section")
            score -= 0.2
        
        # 检查是否有示例
        if "## 示例" not in skill.skill_md_content and "## Examples" not in skill.skill_md_content:
            issues.append("WARNING: Missing examples section")
            score -= 0.1
        
        # 检查是否有使用场景
        if "## 使用场景" not in skill.skill_md_content and "## Usage" not in skill.skill_md_content:
            issues.append("INFO: Missing usage scenarios section")
            score -= 0.05
        
        return max(score, 0), issues
    
    def _validate_quality(self, skill: GeneratedSkill) -> Tuple[float, List[str]]:
        """
        验证质量
        
        基于源模式和历史数据评估质量
        """
        issues = []
        score = 1.0
        
        # 基于源模式评估
        if skill.source_pattern:
            if skill.source_pattern.success_rate < 0.8:
                issues.append(f"WARNING: Low success rate ({skill.source_pattern.success_rate:.1%})")
                score -= 0.2
            
            if skill.source_pattern.frequency < 3:
                issues.append("WARNING: Low frequency pattern (less than 3 occurrences)")
                score -= 0.1
        
        # 检查Token效率
        estimated_tokens = len(skill.skill_md_content.split()) * 1.5
        if estimated_tokens > 2000:
            issues.append(f"WARNING: SKILL.md may be too long (~{estimated_tokens:.0f} tokens)")
            score -= 0.1
        
        # 检查内容长度
        if len(skill.skill_md_content) < 200:
            issues.append("WARNING: SKILL.md content too short")
            score -= 0.1
        elif len(skill.skill_md_content) > 10000:
            issues.append("WARNING: SKILL.md content too long")
            score -= 0.1
        
        return max(score, 0), issues
    
    def validate_skill_name(self, name: str) -> Tuple[bool, List[str]]:
        """
        验证Skill名称
        
        Args:
            name: Skill名称
            
        Returns:
            (是否有效, 问题列表)
        """
        issues = []
        
        # 检查长度
        if len(name) < 3:
            issues.append("Name too short (minimum 3 characters)")
        
        if len(name) > 64:
            issues.append("Name too long (maximum 64 characters)")
        
        # 检查格式
        if not re.match(r'^[a-z0-9-]+$', name):
            issues.append("Name should only contain lowercase letters, numbers, and hyphens")
        
        # 检查不能以连字符开头或结尾
        if name.startswith('-') or name.endswith('-'):
            issues.append("Name should not start or end with hyphen")
        
        # 检查不能有连续连字符
        if '--' in name:
            issues.append("Name should not contain consecutive hyphens")
        
        is_valid = len(issues) == 0
        return is_valid, issues

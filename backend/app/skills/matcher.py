from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
import json

from .base import Skill


@dataclass
class MatchResult:
    skill: Optional[Skill]
    tool_name: Optional[str]
    confidence: float
    reasoning: str
    is_skill_match: bool


class SkillMatcher:
    def __init__(self, llm=None):
        self.llm = llm
    
    def set_llm(self, llm):
        self.llm = llm
    
    async def match(
        self,
        query: str,
        skills: List[Skill],
        available_tools: List[str],
    ) -> MatchResult:
        if not skills and not available_tools:
            return MatchResult(
                skill=None,
                tool_name=None,
                confidence=0.0,
                reasoning="没有可用的 skills 或 tools",
                is_skill_match=False,
            )
        
        skill_summaries = []
        for skill in skills:
            skill_summaries.append({
                "name": skill.meta.name,
                "description": skill.meta.description,
                "tags": skill.meta.tags,
            })
        
        prompt = self._build_classification_prompt(query, skill_summaries, available_tools)
        
        try:
            response = await self.llm.ainvoke(prompt)
            
            result = self._parse_classification_response(response.content, skills)
            
            return result
            
        except Exception as e:
            print(f"LLM classification error: {e}")
            
            return self._fallback_match(query, skills, available_tools)
    
    def _build_classification_prompt(
        self,
        query: str,
        skills: List[Dict],
        tools: List[str],
    ) -> str:
        skills_json = json.dumps(skills, ensure_ascii=False, indent=2)
        tools_json = json.dumps(tools, ensure_ascii=False, indent=2)
        
        return f"""你是一个任务分类器。根据用户的请求，判断应该使用哪个 skill 或 tool 来处理。

用户请求: {query}

可用的 Skills:
{skills_json}

可用的 Tools:
{tools_json}

分类规则:
1. Skills 是复合能力，包含多步骤流程和详细指令
2. Tools 是原子操作，执行单一功能
3. 当请求同时匹配 skill 和 tool 时，优先选择 skill
4. 如果没有匹配的 skill 或 tool，返回 none

请以 JSON 格式返回分类结果:
{{
    "type": "skill" | "tool" | "none",
    "name": "匹配的 skill 或 tool 名称",
    "confidence": 0.0-1.0,
    "reasoning": "选择理由"
}}

只返回 JSON，不要其他内容。"""
    
    def _parse_classification_response(
        self,
        response: str,
        skills: List[Skill],
    ) -> MatchResult:
        try:
            json_match = response
            if "```json" in response:
                json_match = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_match = response.split("```")[1].split("```")[0]
            
            result = json.loads(json_match.strip())
            
            match_type = result.get("type", "none")
            name = result.get("name", "")
            confidence = result.get("confidence", 0.0)
            reasoning = result.get("reasoning", "")
            
            if match_type == "skill":
                matched_skill = next(
                    (s for s in skills if s.meta.name == name),
                    None
                )
                return MatchResult(
                    skill=matched_skill,
                    tool_name=None,
                    confidence=confidence,
                    reasoning=reasoning,
                    is_skill_match=True,
                )
            
            elif match_type == "tool":
                return MatchResult(
                    skill=None,
                    tool_name=name,
                    confidence=confidence,
                    reasoning=reasoning,
                    is_skill_match=False,
                )
            
            else:
                return MatchResult(
                    skill=None,
                    tool_name=None,
                    confidence=confidence,
                    reasoning=reasoning,
                    is_skill_match=False,
                )
                
        except Exception as e:
            print(f"Failed to parse classification response: {e}")
            return MatchResult(
                skill=None,
                tool_name=None,
                confidence=0.0,
                reasoning=f"解析失败: {e}",
                is_skill_match=False,
            )
    
    def _fallback_match(
        self,
        query: str,
        skills: List[Skill],
        tools: List[str],
    ) -> MatchResult:
        query_lower = query.lower()
        
        for skill in skills:
            for tag in skill.meta.tags:
                if tag.lower() in query_lower:
                    return MatchResult(
                        skill=skill,
                        tool_name=None,
                        confidence=0.6,
                        reasoning=f"关键词匹配: {tag}",
                        is_skill_match=True,
                    )
        
        for tool in tools:
            if tool.lower() in query_lower:
                return MatchResult(
                    skill=None,
                    tool_name=tool,
                    confidence=0.5,
                    reasoning=f"工具名称匹配",
                    is_skill_match=False,
                )
        
        return MatchResult(
            skill=None,
            tool_name=None,
            confidence=0.0,
            reasoning="无匹配",
            is_skill_match=False,
        )
    
    def match_by_keywords(self, query: str, skills: List[Skill]) -> List[Skill]:
        matched = []
        query_lower = query.lower()
        
        for skill in skills:
            for tag in skill.meta.tags:
                if tag.lower() in query_lower:
                    matched.append(skill)
                    break
            
            keywords = skill.meta.matching.get("keywords", [])
            for kw in keywords:
                if kw.lower() in query_lower:
                    matched.append(skill)
                    break
        
        return matched

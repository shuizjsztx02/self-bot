from typing import List, Optional, Dict, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
import json
import logging

from .base import Skill

if TYPE_CHECKING:
    from .clawhub import ClawHubClient, ClawHubSkill
    from .manager import SkillManager
    from .dependency_resolver import DependencyCheckResult

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    skill: Optional[Skill]
    tool_name: Optional[str]
    confidence: float
    reasoning: str
    is_skill_match: bool
    pending_dependencies: Optional["DependencyCheckResult"] = None


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

        # 无 LLM 时直接使用关键词降级匹配
        if not self.llm:
            return self._fallback_match(query, skills, available_tools)

        prompt = self._build_classification_prompt(query, skill_summaries, available_tools)

        try:
            response = await self.llm.ainvoke(prompt)
            result = self._parse_classification_response(response.content, skills)
            return result

        except Exception as e:
            logger.warning(f"LLM classification error: {e}")
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
    
    async def match_with_clawhub_fallback(
        self,
        query: str,
        local_skills: List[Skill],
        available_tools: List[str],
        clawhub_client: "ClawHubClient",
        skill_manager: "SkillManager",
        auto_install: bool = True,
        min_confidence: float = 0.6,
        search_limit: int = 3,
    ) -> MatchResult:
        """
        带 ClawHub 降级的技能匹配。

        流程：
        1. 先在本地技能中匹配
        2. 本地无匹配时，自动搜索 ClawHub
        3. 使用 LLM 判断搜索结果是否合适
        4. 置信度达标时自动安装并激活
        """
        # 第一步：本地匹配
        if local_skills or available_tools:
            local_result = await self.match(query, local_skills, available_tools)
            if local_result.is_skill_match and local_result.skill:
                logger.info(
                    f"[SkillMatcher] 本地技能匹配成功: {local_result.skill.meta.name} "
                    f"(置信度: {local_result.confidence:.2f})"
                )
                return local_result
        else:
            local_result = MatchResult(
                skill=None, tool_name=None, confidence=0.0,
                reasoning="本地无技能", is_skill_match=False,
            )

        # 第二步：ClawHub 降级搜索
        logger.info(f"[SkillMatcher] 本地无匹配，搜索 ClawHub: {query[:80]}")
        try:
            remote_skills = await clawhub_client.search(query, limit=search_limit)
        except Exception as e:
            logger.warning(f"[SkillMatcher] ClawHub 搜索失败: {e}")
            return local_result

        if not remote_skills:
            logger.info("[SkillMatcher] ClawHub 无搜索结果")
            return local_result

        # 第三步：LLM 判断最合适的远程技能
        best = await self._judge_remote_skills(query, remote_skills)
        if not best or best.get("confidence", 0) < min_confidence:
            logger.info(
                f"[SkillMatcher] ClawHub 结果置信度不足: "
                f"{best.get('confidence', 0) if best else 0:.2f} < {min_confidence}"
            )
            return local_result

        slug = best["slug"]
        confidence = best["confidence"]
        reason = best.get("reason", f"ClawHub 技能 {slug} 与需求匹配")

        # 第四步：自动安装
        if auto_install:
            logger.info(f"[SkillMatcher] 自动安装 ClawHub 技能: {slug} (置信度: {confidence:.2f})")
            try:
                skill = await skill_manager.install_skill_from_clawhub(slug, activate=True)
                if skill:
                    # 第五步：依赖检测
                    from .dependency_resolver import DependencyResolver
                    resolver = DependencyResolver(available_tool_names=available_tools)
                    dep_check = await resolver.check(skill)

                    if not dep_check.satisfied:
                        logger.info(
                            f"[SkillMatcher] 技能已下载但依赖不满足: "
                            f"{dep_check.summary()}"
                        )
                        return MatchResult(
                            skill=skill,
                            tool_name=None,
                            confidence=confidence,
                            reasoning=f"[ClawHub 已下载，待安装依赖] {reason}",
                            is_skill_match=True,
                            pending_dependencies=dep_check,
                        )

                    logger.info(f"[SkillMatcher] 技能安装并激活成功: {skill.meta.name}")
                    return MatchResult(
                        skill=skill,
                        tool_name=None,
                        confidence=confidence,
                        reasoning=f"[ClawHub 自动安装] {reason}",
                        is_skill_match=True,
                    )
                else:
                    logger.warning(f"[SkillMatcher] 技能安装失败: {slug}")
            except Exception as e:
                logger.error(f"[SkillMatcher] 自动安装异常: {e}")

        # 安装失败，返回搜索到但未安装的信息
        return MatchResult(
            skill=None,
            tool_name=None,
            confidence=confidence,
            reasoning=f"[ClawHub 发现未安装] {slug}: {reason}",
            is_skill_match=False,
        )

    async def _judge_remote_skills(
        self,
        query: str,
        remote_skills: List["ClawHubSkill"],
    ) -> Optional[Dict]:
        """使用 LLM 判断搜索结果中哪个技能最合适（无 LLM 时取第一个）"""
        if not remote_skills:
            return None

        # 无 LLM 时简单取第一个，置信度设为 0.7
        if not self.llm:
            first = remote_skills[0]
            return {"slug": first.slug, "confidence": 0.7, "reason": f"默认选择: {first.name}"}

        skill_list_text = "\n".join([
            f"- slug: {s.slug}, name: {s.name}, description: {s.description}"
            for s in remote_skills
        ])

        prompt = f"""你是技能匹配专家。请根据用户需求判断哪个 ClawHub 技能最合适。

用户需求: {query}

可用技能:
{skill_list_text}

要求：
1. 选出最合适的技能（如果都不合适，confidence 设为 0）
2. confidence 范围 0.0-1.0
3. 只返回 JSON，不要其他内容

返回格式:
{{"slug": "技能slug", "confidence": 0.0-1.0, "reason": "选择理由（一句话）"}}"""

        try:
            response = await self.llm.ainvoke(prompt)
            text = response.content if hasattr(response, "content") else str(response)

            # 提取 JSON
            import re
            match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if match:
                result = json.loads(match.group())
                if result.get("slug"):
                    return result
        except Exception as e:
            logger.warning(f"[SkillMatcher] LLM 判断异常: {e}")
            # 降级：取第一个
            if remote_skills:
                first = remote_skills[0]
                return {"slug": first.slug, "confidence": 0.65, "reason": f"LLM 不可用，默认选择: {first.name}"}

        return None

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

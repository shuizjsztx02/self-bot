from typing import Dict, List, Optional, Any, Tuple, Union
from pathlib import Path
from datetime import datetime
import asyncio

from .base import Skill, SkillTool, DANGEROUS_TOOLS
from .loader import SkillLoader
from .matcher import SkillMatcher, MatchResult


class SkillManager:
    def __init__(
        self,
        skills_dir: Union[str, List[str]] = "./skills",
        llm=None,
        enable_watcher: bool = False,
    ):
        self.loader = SkillLoader(skills_dir, enable_watcher)
        self.matcher = SkillMatcher(llm)
        self.llm = llm
        
        self._active_skills: Dict[str, Skill] = {}
        self._skill_tools: Dict[str, SkillTool] = {}
        self._initialized = False
    
    async def initialize(self):
        if self._initialized:
            return
        
        await self.loader.load_all()
        
        if self.loader.enable_watcher:
            await self.loader.start_watcher()
        
        self._initialized = True
    
    def set_llm(self, llm):
        self.llm = llm
        self.matcher.set_llm(llm)
    
    def add_skills_directory(self, dir_path: str):
        self.loader.add_skills_dir(dir_path)
    
    async def get_skill(self, name: str) -> Optional[Skill]:
        cached = self.loader.get_cached(name)
        if cached:
            return cached
        
        return await self.loader.load_by_name(name)
    
    def get_all_skills(self) -> Dict[str, Skill]:
        return self.loader.get_all_cached()
    
    def get_skill_summaries(self) -> List[Dict]:
        return self.loader.get_skill_summaries()
    
    async def match_request(
        self,
        query: str,
        available_tools: List[str],
    ) -> MatchResult:
        skills = list(self.loader.get_all_cached().values())
        enabled_skills = [s for s in skills if s.meta.enabled]
        
        if self.llm:
            return await self.matcher.match(query, enabled_skills, available_tools)
        else:
            return self.matcher._fallback_match(query, enabled_skills, available_tools)
    
    def activate_skill(self, skill_name: str) -> bool:
        skill = self.loader.get_cached(skill_name)
        if skill:
            self._active_skills[skill_name] = skill
            return True
        return False
    
    def deactivate_skill(self, skill_name: str) -> bool:
        if skill_name in self._active_skills:
            del self._active_skills[skill_name]
            return True
        return False
    
    def get_active_skills(self) -> List[Skill]:
        return list(self._active_skills.values())
    
    def check_tool_permission(
        self,
        tool_name: str,
        skill: Optional[Skill] = None,
    ) -> Tuple[bool, str]:
        if tool_name in DANGEROUS_TOOLS:
            return False, f"工具 '{tool_name}' 被标记为危险工具，需要特殊权限"
        
        if skill:
            if not skill.has_tool_permission(tool_name):
                return False, f"Skill '{skill.meta.name}' 无权使用工具 '{tool_name}'"
        
        return True, ""
    
    def build_skill_prompt(self, skills: List[Skill]) -> str:
        if not skills:
            return ""
        
        parts = []
        
        for skill in skills:
            parts.append(f"""
## 激活的 Skill: {skill.meta.name}

{skill.instructions}

""")
        
        return "\n".join(parts)
    
    async def create_skill(
        self,
        name: str,
        description: str,
        instructions: str,
        tags: List[str] = None,
        permissions: Dict = None,
    ) -> Optional[Skill]:
        from .base import SkillMeta
        
        if self.loader.skills_dirs:
            skill_dir = self.loader.skills_dirs[0] / name.replace("-", "_")
        else:
            skill_dir = Path("./skills") / name.replace("-", "_")
        
        skill_dir.mkdir(parents=True, exist_ok=True)
        
        skill_path = skill_dir / "SKILL.md"
        
        frontmatter = {
            "name": name,
            "description": description,
            "version": "1.0.0",
            "tags": tags or [],
            "permissions": permissions or {},
        }
        
        import yaml
        frontmatter_str = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False)
        
        content = f"---\n{frontmatter_str}---\n\n{instructions}"
        
        try:
            import aiofiles
            async with aiofiles.open(skill_path, "w", encoding="utf-8") as f:
                await f.write(content)
            
            skill = await self.loader.load(skill_path)
            return skill
            
        except Exception as e:
            print(f"Failed to create skill: {e}")
            return None
    
    async def delete_skill(self, name: str) -> bool:
        skill = self.loader.get_cached(name)
        if not skill:
            return False
        
        try:
            import shutil
            skill_dir = skill.path.parent
            shutil.rmtree(skill_dir)
            
            if name in self.loader._cache:
                del self.loader._cache[name]
            
            if name in self._active_skills:
                del self._active_skills[name]
            
            return True
            
        except Exception as e:
            print(f"Failed to delete skill: {e}")
            return False
    
    def register_skill_tool(self, tool: SkillTool):
        self._skill_tools[tool.name] = tool
    
    def get_skill_tools(self) -> Dict[str, SkillTool]:
        return self._skill_tools.copy()
    
    async def create_tool_for_skill(
        self,
        skill_name: str,
        tool_name: str,
        description: str,
        parameters: Dict,
    ) -> Optional[SkillTool]:
        skill = self.loader.get_cached(skill_name)
        if not skill:
            return None
        
        tool = SkillTool(
            name=tool_name,
            description=description,
            parameters=parameters,
            implementation="",
        )
        
        self._skill_tools[f"{skill_name}.{tool_name}"] = tool
        
        return tool

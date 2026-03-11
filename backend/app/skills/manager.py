from typing import Dict, List, Optional, Any, Tuple, Union
from pathlib import Path
from datetime import datetime
import asyncio
import logging

from .base import Skill, SkillTool, DANGEROUS_TOOLS
from .loader import SkillLoader
from .matcher import SkillMatcher, MatchResult
from .tracer import get_skill_tracer, skill_trace_step
from .clawhub import ClawHubClient, ClawHubSkill

logger = logging.getLogger(__name__)


class SkillManager:
    def __init__(
        self,
        skills_dir: Union[str, List[str]] = "./skills",
        llm=None,
        enable_watcher: bool = False,
        clawhub_install_dir: str = "./skills/installed",
        enable_clawhub: bool = True,
        clawhub_mock_mode: bool = False,
    ):
        self.loader = SkillLoader(skills_dir, enable_watcher)
        self.matcher = SkillMatcher(llm)
        self.llm = llm
        
        self._active_skills: Dict[str, Skill] = {}
        self._skill_tools: Dict[str, SkillTool] = {}
        self._initialized = False
        
        self.enable_clawhub = enable_clawhub
        self.clawhub: Optional[ClawHubClient] = None
        
        if enable_clawhub:
            self.clawhub = ClawHubClient(
                install_dir=clawhub_install_dir,
                mock_mode=clawhub_mock_mode,
            )
            self.loader.add_skills_dir(clawhub_install_dir)
    
    async def initialize(self):
        with skill_trace_step("initialize", "manager", {}):
            if self._initialized:
                return
            
            await self.loader.load_all()
            
            if self.loader.enable_watcher:
                await self.loader.start_watcher()
            
            self._initialized = True
            
            skills_count = len(self.loader.get_all_cached())
            get_skill_tracer().trace("initialized", "manager", {
                "skills_count": skills_count,
            })
    
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
    
    async def match_request_with_clawhub_fallback(
        self,
        query: str,
        available_tools: List[str],
        auto_install: bool = True,
        min_confidence: float = 0.6,
        search_limit: int = 3,
    ) -> MatchResult:
        """
        带 ClawHub 降级的技能匹配。

        本地无匹配时自动搜索 ClawHub，下载并激活合适的技能。
        """
        skills = list(self.loader.get_all_cached().values())
        enabled_skills = [s for s in skills if s.meta.enabled]

        if not self.clawhub:
            # 无 ClawHub 客户端，退化为普通匹配
            return await self.match_request(query, available_tools)

        result = await self.matcher.match_with_clawhub_fallback(
            query=query,
            local_skills=enabled_skills,
            available_tools=available_tools,
            clawhub_client=self.clawhub,
            skill_manager=self,
            auto_install=auto_install,
            min_confidence=min_confidence,
            search_limit=search_limit,
        )

        get_skill_tracer().trace("match_with_clawhub_fallback", "matcher", {
            "matched_skill": result.skill.meta.name if result.skill else None,
            "confidence": result.confidence,
            "is_skill_match": result.is_skill_match,
            "reasoning": result.reasoning[:120] if result.reasoning else None,
        })

        return result

    async def match_request(
        self,
        query: str,
        available_tools: List[str],
    ) -> MatchResult:
        with skill_trace_step("match_request", "manager", {
            "query": query[:100] + "..." if len(query) > 100 else query,
            "available_tools_count": len(available_tools),
        }):
            skills = list(self.loader.get_all_cached().values())
            enabled_skills = [s for s in skills if s.meta.enabled]
            
            if self.llm:
                result = await self.matcher.match(query, enabled_skills, available_tools)
            else:
                result = self.matcher._fallback_match(query, enabled_skills, available_tools)
            
            get_skill_tracer().trace("match_result", "matcher", {
                "matched_skill": result.skill.meta.name if result.skill else None,
                "matched_tool": result.tool_name,
                "confidence": result.confidence,
                "is_skill_match": result.is_skill_match,
                "reasoning": result.reasoning[:100] if result.reasoning else None,
            })
            
            return result
    
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
        skill_names = [s.meta.name for s in skills]
        
        with skill_trace_step("build_skill_prompt", "prompt", {
            "skills": skill_names,
            "skills_count": len(skills),
        }):
            if not skills:
                return ""
            
            parts = []
            
            for skill in skills:
                skill_prompt = f"""
## 激活的 Skill: {skill.meta.name}

{skill.instructions}

"""
                parts.append(skill_prompt)
                
                get_skill_tracer().trace("skill_prompt_injected", "prompt", {
                    "skill_name": skill.meta.name,
                    "instructions_len": len(skill.instructions),
                    "description": skill.meta.description,
                })
            
            result = "\n".join(parts)
            
            get_skill_tracer().trace("skill_prompt_built", "prompt", {
                "total_len": len(result),
                "skills_count": len(skills),
            })
            
            return result
    
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
    
    async def search_remote_skills(
        self,
        query: str,
        limit: int = 10
    ) -> List[ClawHubSkill]:
        """
        搜索 ClawHub 技能
        
        Args:
            query: 搜索关键词
            limit: 返回数量
        
        Returns:
            技能列表
        """
        if not self.clawhub:
            return []
        
        skills = await self.clawhub.search(query, limit)
        
        installed = self.clawhub.list_installed()
        for skill in skills:
            skill.installed = skill.slug in installed
            if skill.installed:
                skill.installed_version = self.clawhub.get_installed_version(skill.slug)
        
        return skills
    
    async def install_skill_from_clawhub(
        self,
        slug: str,
        activate: bool = True,
        version: str = None
    ) -> Optional[Skill]:
        """
        从 ClawHub 安装技能
        
        Args:
            slug: 技能标识符
            activate: 是否激活
            version: 指定版本
        
        Returns:
            安装的技能对象
        """
        if not self.clawhub:
            logger.warning("ClawHub is not enabled")
            return None
        
        skill_path = self.clawhub.get_skill_path(slug)
        if skill_path and skill_path.exists():
            logger.info(f"Skill already installed: {slug}")
            skill = await self.loader.load(skill_path)
            if skill:
                skill._clawhub_slug = slug
                self._clawhub_slug_to_name = getattr(self, '_clawhub_slug_to_name', {})
                self._clawhub_slug_to_name[slug] = skill.meta.name
                if activate:
                    self.activate_skill(skill.meta.name)
            return skill
        
        success = await self.clawhub.install(slug, version=version)
        
        if not success:
            logger.error(f"Failed to install skill: {slug}")
            return None
        
        skill_path = self.clawhub.get_skill_path(slug)
        
        if not skill_path:
            logger.error(f"SKILL.md not found after install: {slug}")
            return None
        
        skill = await self.loader.load(skill_path)
        
        if skill:
            skill._clawhub_slug = slug
            self._clawhub_slug_to_name = getattr(self, '_clawhub_slug_to_name', {})
            self._clawhub_slug_to_name[slug] = skill.meta.name

            # 下载完成后自动安装可自动安装的依赖（pip、npm、bins、mcp）
            await self._auto_install_dependencies(skill)

            get_skill_tracer().trace("clawhub_install", "manager", {
                "slug": slug,
                "name": skill.meta.name,
                "version": skill.meta.version,
                "activated": activate,
            })
            
            if activate:
                self.activate_skill(skill.meta.name)
        
        return skill

    async def _auto_install_dependencies(self, skill: Skill) -> None:
        """
        技能下载后自动安装可自动安装的依赖（pip、npm、bins、mcp）。
        env 类依赖需用户手动配置，不在此处理。
        """
        from .dependency_resolver import DependencyResolver
        from .dependency_installer import DependencyInstaller

        resolver = DependencyResolver()
        check = await resolver.check(skill)
        if check.satisfied:
            return

        logger.info(
            f"[SkillManager] 技能 {skill.meta.name} 下载完成，自动安装依赖: {check.summary()}"
        )
        installer = DependencyInstaller()
        try:
            # 仅安装可自动安装的项，env 需用户后续在对话框中填写
            result = await installer.install_all(
                check, progress_callback=None, skill=skill
            )
            if result.success:
                logger.info(
                    f"[SkillManager] 技能 {skill.meta.name} 依赖自动安装完成"
                )
            elif result.errors:
                logger.warning(
                    f"[SkillManager] 技能 {skill.meta.name} 部分依赖安装失败: "
                    f"{', '.join(result.errors)}"
                )
        except Exception as e:
            logger.warning(f"[SkillManager] 依赖自动安装异常: {e}")
    
    async def uninstall_skill_from_clawhub(
        self,
        slug: str
    ) -> bool:
        """
        从 ClawHub 卸载技能
        
        Args:
            slug: 技能标识符
        
        Returns:
            是否成功
        """
        if not self.clawhub:
            return False
        
        if slug in self.loader._cache:
            del self.loader._cache[slug]
        
        if slug in self._active_skills:
            del self._active_skills[slug]
        
        success = await self.clawhub.uninstall(slug)
        
        if success:
            get_skill_tracer().trace("clawhub_uninstall", "manager", {
                "slug": slug,
            })
        
        return success
    
    async def update_skill_from_clawhub(
        self,
        slug: str = None,
        update_all: bool = False
    ) -> Dict[str, bool]:
        """
        更新 ClawHub 技能
        
        Args:
            slug: 技能标识符（更新单个）
            update_all: 是否更新所有
        
        Returns:
            更新结果
        """
        if not self.clawhub:
            return {}
        
        results = await self.clawhub.update(slug=slug, all_skills=update_all)
        
        for skill_slug, success in results.items():
            if success:
                await self.loader.reload(skill_slug)
        
        return results
    
    def get_clawhub_client(self) -> Optional[ClawHubClient]:
        """获取 ClawHub 客户端"""
        return self.clawhub
    
    async def get_popular_skills(self, limit: int = 10) -> List[ClawHubSkill]:
        """获取热门技能"""
        if not self.clawhub:
            return []
        return await self.clawhub.get_popular(limit)
    
    def list_installed_from_clawhub(self) -> List[str]:
        """列出从 ClawHub 安装的技能"""
        if not self.clawhub:
            return []
        return self.clawhub.list_installed()
    
    def get_skill_by_slug(self, slug: str) -> Optional[Skill]:
        """通过 slug 查找已加载的技能（先查 slug->name 映射，再遍历缓存）"""
        slug_to_name = getattr(self, '_clawhub_slug_to_name', {})
        name = slug_to_name.get(slug)
        if name:
            cached = self.loader.get_cached(name)
            if cached:
                return cached

        for skill in self.loader.get_all_cached().values():
            normalized = skill.meta.name.lower().replace(' ', '-')
            if normalized == slug.lower():
                return skill

        return None

    def get_skill_source(self, skill_name: str) -> str:
        """
        获取技能来源
        
        Args:
            skill_name: 技能名称或 slug
        
        Returns:
            "local" | "clawhub" | "unknown"
        """
        clawhub_installed = self.list_installed_from_clawhub()
        if skill_name in clawhub_installed:
            return "clawhub"
        
        all_skills = self.get_all_skills()
        if skill_name in all_skills:
            return "local"
        
        slug_to_name = getattr(self, '_clawhub_slug_to_name', {})
        if skill_name in slug_to_name:
            return "clawhub"
        
        for slug in clawhub_installed:
            if slug.replace('-', ' ').lower() == skill_name.replace('-', ' ').lower():
                return "clawhub"
        
        return "unknown"

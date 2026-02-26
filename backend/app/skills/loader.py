from pathlib import Path
from typing import Dict, List, Optional, Union
from datetime import datetime
import asyncio
import aiofiles
from watchfiles import awatch

from .base import Skill, SkillParser


class SkillLoader:
    def __init__(
        self,
        skills_dir: Union[str, List[str]] = "./skills",
        enable_watcher: bool = False,
    ):
        if isinstance(skills_dir, str):
            self.skills_dirs = [Path(skills_dir)]
        else:
            self.skills_dirs = [Path(d) for d in skills_dir]
        
        self.enable_watcher = enable_watcher
        self._cache: Dict[str, Skill] = {}
        self._last_modified: Dict[str, datetime] = {}
        self._watcher_task: Optional[asyncio.Task] = None
    
    def discover_skills(self) -> List[Path]:
        skill_files = []
        
        for skills_dir in self.skills_dirs:
            if not skills_dir.exists():
                continue
            
            for skill_file in skills_dir.rglob("SKILL.md"):
                skill_files.append(skill_file)
        
        return skill_files
    
    async def load(self, skill_path: Path) -> Optional[Skill]:
        try:
            async with aiofiles.open(skill_path, "r", encoding="utf-8") as f:
                content = await f.read()
            
            skill = SkillParser.parse_skill_md(content, skill_path)
            
            if skill:
                self._cache[skill.meta.name] = skill
                self._last_modified[str(skill_path)] = datetime.now()
            
            return skill
            
        except Exception as e:
            print(f"Error loading skill {skill_path}: {e}")
            return None
    
    async def load_all(self) -> Dict[str, Skill]:
        skills = {}
        skill_files = self.discover_skills()
        
        for skill_path in skill_files:
            skill = await self.load(skill_path)
            if skill:
                skills[skill.meta.name] = skill
        
        return skills
    
    async def load_by_name(self, name: str) -> Optional[Skill]:
        if name in self._cache:
            return self._cache[name]
        
        for skill_path in self.discover_skills():
            skill = await self.load(skill_path)
            if skill and skill.meta.name == name:
                return skill
        
        return None
    
    def get_cached(self, name: str) -> Optional[Skill]:
        return self._cache.get(name)
    
    def get_all_cached(self) -> Dict[str, Skill]:
        return self._cache.copy()
    
    def clear_cache(self):
        self._cache.clear()
        self._last_modified.clear()
    
    async def reload(self, name: str) -> Optional[Skill]:
        if name in self._cache:
            del self._cache[name]
        
        return await self.load_by_name(name)
    
    async def start_watcher(self):
        if not self.enable_watcher:
            return
        
        self._watcher_task = asyncio.create_task(self._watch_loop())
    
    async def stop_watcher(self):
        if self._watcher_task:
            self._watcher_task.cancel()
            try:
                await self._watcher_task
            except asyncio.CancelledError:
                pass
            self._watcher_task = None
    
    async def _watch_loop(self):
        for skills_dir in self.skills_dirs:
            async for changes in awatch(str(skills_dir)):
                for change_type, path_str in changes:
                    path = Path(path_str)
                    
                    if path.name == "SKILL.md":
                        if change_type == 1:
                            await self.load(path)
                            print(f"Skill loaded: {path}")
                        elif change_type == 2:
                            await self.load(path)
                            print(f"Skill reloaded: {path}")
                        elif change_type == 3:
                            skill_name = self._find_skill_name_by_path(path)
                            if skill_name and skill_name in self._cache:
                                del self._cache[skill_name]
                                print(f"Skill removed: {skill_name}")
    
    def _find_skill_name_by_path(self, path: Path) -> Optional[str]:
        for name, skill in self._cache.items():
            if skill.path == path:
                return name
        return None
    
    def get_skill_summaries(self) -> List[Dict]:
        summaries = []
        for name, skill in self._cache.items():
            summaries.append({
                "name": skill.meta.name,
                "description": skill.meta.description,
                "tags": skill.meta.tags,
                "enabled": skill.meta.enabled,
            })
        return summaries
    
    def add_skills_dir(self, dir_path: str):
        path = Path(dir_path)
        if path not in self.skills_dirs:
            self.skills_dirs.append(path)

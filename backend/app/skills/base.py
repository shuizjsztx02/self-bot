from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from pathlib import Path
from datetime import datetime
import re
import yaml


DANGEROUS_TOOLS = {
    "delete_file": "删除文件",
    "execute_code": "执行任意代码",
    "move_file": "移动文件",
}


@dataclass
class SkillMeta:
    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""
    tags: List[str] = field(default_factory=list)
    priority: int = 0
    enabled: bool = True
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    matching: Dict[str, List[str]] = field(default_factory=dict)
    permissions: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "tags": self.tags,
            "priority": self.priority,
            "enabled": self.enabled,
            "dependencies": self.dependencies,
            "matching": self.matching,
            "permissions": self.permissions,
        }


@dataclass
class Skill:
    meta: SkillMeta
    content: str
    instructions: str
    path: Path
    loaded_at: datetime = field(default_factory=datetime.now)
    
    def get_allowed_tools(self) -> List[str]:
        return self.meta.permissions.get("allowed_tools", [])
    
    def get_forbidden_tools(self) -> List[str]:
        return self.meta.permissions.get("forbidden_tools", [])
    
    def has_tool_permission(self, tool_name: str) -> bool:
        forbidden = self.get_forbidden_tools()
        if tool_name in forbidden:
            return False
        
        allowed = self.get_allowed_tools()
        if not allowed:
            return True
        
        return tool_name in allowed
    
    def to_dict(self) -> dict:
        return {
            "meta": self.meta.to_dict(),
            "content": self.content[:500] + "..." if len(self.content) > 500 else self.content,
            "path": str(self.path),
            "loaded_at": self.loaded_at.isoformat(),
        }


@dataclass
class SkillTool:
    name: str
    description: str
    parameters: Dict[str, Any]
    implementation: str
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class SkillParser:
    @staticmethod
    def parse_skill_md(content: str, path: Path) -> Optional[Skill]:
        try:
            frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
            
            if not frontmatter_match:
                print(f"Invalid SKILL.md format: {path}")
                return None
            
            frontmatter_str = frontmatter_match.group(1)
            instructions = frontmatter_match.group(2).strip()
            
            frontmatter = yaml.safe_load(frontmatter_str)
            
            if not frontmatter.get("name"):
                print(f"Missing required field 'name' in: {path}")
                return None
            
            if not frontmatter.get("description"):
                print(f"Missing required field 'description' in: {path}")
                return None
            
            meta = SkillMeta(
                name=frontmatter.get("name", ""),
                description=frontmatter.get("description", ""),
                version=frontmatter.get("version", "1.0.0"),
                author=frontmatter.get("author", ""),
                tags=frontmatter.get("tags", []),
                priority=frontmatter.get("priority", 0),
                enabled=frontmatter.get("enabled", True),
                dependencies=frontmatter.get("dependencies", {}),
                matching=frontmatter.get("matching", {}),
                permissions=frontmatter.get("permissions", {}),
            )
            
            return Skill(
                meta=meta,
                content=content,
                instructions=instructions,
                path=path,
            )
            
        except Exception as e:
            print(f"Error parsing skill {path}: {e}")
            return None
    
    @staticmethod
    def parse_tool_definition(content: str) -> List[SkillTool]:
        tools = []
        
        tool_pattern = re.compile(
            r'##\s*Tool:\s*(\w+)\s*\n'
            r'(?:###\s*Description\s*\n(.*?)\n)?'
            r'(?:###\s*Parameters\s*\n```json\s*\n(.*?)\n```)?',
            re.DOTALL
        )
        
        for match in tool_pattern.finditer(content):
            name = match.group(1)
            description = match.group(2) or ""
            params_str = match.group(3) or "{}"
            
            try:
                parameters = yaml.safe_load(params_str) if params_str else {}
            except:
                parameters = {}
            
            tools.append(SkillTool(
                name=name,
                description=description.strip(),
                parameters=parameters,
                implementation="",
            ))
        
        return tools

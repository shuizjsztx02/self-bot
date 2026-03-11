from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Set
from pathlib import Path
from datetime import datetime
import json
import re
import yaml


DANGEROUS_TOOLS = {
    "delete_file": "删除文件",
    "execute_code": "执行任意代码",
    "move_file": "移动文件",
}


@dataclass
class SkillDependencies:
    """技能依赖声明（标准化结构）"""
    pip: List[str] = field(default_factory=list)
    npm: List[str] = field(default_factory=list)
    mcp_servers: List[Dict[str, Any]] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    env: List[str] = field(default_factory=list)
    bins: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Any) -> "SkillDependencies":
        if not data or not isinstance(data, dict):
            return cls()
        return cls(
            pip=data.get("pip", []) or [],
            npm=data.get("npm", []) or [],
            mcp_servers=data.get("mcp_servers", []) or [],
            tools=data.get("tools", []) or [],
            env=data.get("env", []) or [],
            bins=data.get("bins", []) or [],
        )

    def to_dict(self) -> dict:
        return {
            "pip": self.pip,
            "npm": self.npm,
            "mcp_servers": self.mcp_servers,
            "tools": self.tools,
            "env": self.env,
            "bins": self.bins,
        }

    def has_any(self) -> bool:
        return bool(self.pip or self.npm or self.mcp_servers or self.tools or self.env or self.bins)


@dataclass
class SkillMeta:
    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""
    tags: List[str] = field(default_factory=list)
    priority: int = 0
    enabled: bool = True
    dependencies: Dict[str, Any] = field(default_factory=dict)
    matching: Dict[str, List[str]] = field(default_factory=dict)
    permissions: Dict[str, Any] = field(default_factory=dict)
    # 安装指令（来自 metadata.clawdbot.install / metadata.openclaw.install）
    install_instructions: List[Dict[str, Any]] = field(default_factory=list)

    def get_dependencies(self) -> SkillDependencies:
        """将原始 dependencies dict 解析为 SkillDependencies 结构"""
        return SkillDependencies.from_dict(self.dependencies)

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
            "install_instructions": self.install_instructions,
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
    # 从正文中识别 API Key / Token 类环境变量（全大写 + 常见后缀）
    _ENV_RE = re.compile(
        r'\b([A-Z][A-Z0-9_]{3,}_(?:KEY|TOKEN|SECRET|API_KEY|PASSWORD|URL))\b'
    )
    # 排除明显不是环境变量的误匹配
    _ENV_EXCLUDE = {
        "YOUR_TOKEN", "YOUR_API_KEY", "YOUR_SECRET", "YOUR_KEY",
        "YOUR_SECRET_KEY", "YOUR_PASSWORD", "CACHE_KEY",
        "ITEM_ID", "OPTION_ID", "GIST_ID", "FIELD_ID",
        "FIELD_NODE_ID", "ITEM_NODE_ID", "PROJECT_ID",
        "ITERATION_ID", "RULESET_ID", "STATUS_FIELD_ID",
        "TODO_OPTION_ID",
    }
    _PIP_RE = re.compile(r'pip3?\s+install\s+([\w\-\[\]>=<.]+)', re.IGNORECASE)
    _NPM_RE = re.compile(r'npm\s+install\s+(?:-[gD]\s+)?([@\w/\->=<.]+)', re.IGNORECASE)

    @classmethod
    def _extract_body_deps(cls, body: str) -> Dict[str, Any]:
        """从 SKILL.md 正文中扫描隐性依赖声明"""
        env_vars: Set[str] = set()
        pip_pkgs: Set[str] = set()
        npm_pkgs: Set[str] = set()

        for m in cls._ENV_RE.finditer(body):
            var = m.group(1)
            if var not in cls._ENV_EXCLUDE:
                env_vars.add(var)

        for m in cls._PIP_RE.finditer(body):
            pkg = m.group(1).strip()
            if pkg and not pkg.startswith("-"):
                pip_pkgs.add(pkg)

        for m in cls._NPM_RE.finditer(body):
            pkg = m.group(1).strip()
            if pkg and not pkg.startswith("-"):
                npm_pkgs.add(pkg)

        result: Dict[str, Any] = {}
        if env_vars:
            result["env"] = sorted(env_vars)
        if pip_pkgs:
            result["pip"] = sorted(pip_pkgs)
        if npm_pkgs:
            result["npm"] = sorted(npm_pkgs)
        return result

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
            
            # ── 来源 1：显式 dependencies 字段 ──
            dependencies = frontmatter.get("dependencies", {}) or {}

            # ── 来源 2：ClawHub metadata requires（支持 clawdbot / openclaw 两种命名空间）──
            clawhub_metadata = frontmatter.get("metadata", {})
            if isinstance(clawhub_metadata, str):
                try:
                    clawhub_metadata = json.loads(clawhub_metadata)
                except Exception:
                    clawhub_metadata = {}
            install_instructions: List[Dict[str, Any]] = []
            if isinstance(clawhub_metadata, dict):
                for ns_key in ("clawdbot", "openclaw"):
                    ns_data = clawhub_metadata.get(ns_key, {})
                    if not isinstance(ns_data, dict):
                        continue
                    requires = ns_data.get("requires", {})
                    if not isinstance(requires, dict):
                        continue
                    for key in ("env", "pip", "npm", "tools", "mcp_servers", "bins"):
                        if key in requires and key not in dependencies:
                            dependencies[key] = requires[key]
                        elif key in requires and key in dependencies:
                            existing = set(dependencies[key]) if isinstance(dependencies[key], list) else set()
                            new_vals = requires[key] if isinstance(requires[key], list) else []
                            dependencies[key] = list(existing | set(new_vals))
                    # 解析 install 安装指令（用于 bins 自动安装）
                    inst = ns_data.get("install", [])
                    if isinstance(inst, list) and not install_instructions:
                        for item in inst:
                            if isinstance(item, dict) and item.get("kind"):
                                install_instructions.append(item)

            # ── 来源 3：从正文内容中扫描隐性依赖 ──
            body_deps = SkillParser._extract_body_deps(instructions)
            for key, vals in body_deps.items():
                if key not in dependencies:
                    dependencies[key] = vals
                elif isinstance(dependencies[key], list):
                    existing = set(dependencies[key])
                    dependencies[key] = list(existing | set(vals))

            meta = SkillMeta(
                name=frontmatter.get("name", ""),
                description=frontmatter.get("description", ""),
                version=frontmatter.get("version", "1.0.0"),
                author=frontmatter.get("author", ""),
                tags=frontmatter.get("tags", []),
                priority=frontmatter.get("priority", 0),
                enabled=frontmatter.get("enabled", True),
                dependencies=dependencies,
                matching=frontmatter.get("matching", {}),
                permissions=frontmatter.get("permissions", {}),
                install_instructions=install_instructions,
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

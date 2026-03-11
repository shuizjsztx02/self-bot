from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional

from langchain_core.tools import BaseTool


class ToolSource(str, Enum):
    """工具来源"""
    LOCAL = "local"
    MCP = "mcp"
    SKILL = "skill"
    CUSTOM = "custom"


class ToolStatus(str, Enum):
    """工具状态"""
    REGISTERED = "registered"
    LOADED = "loaded"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class ToolMetadata:
    """工具元数据"""
    name: str
    description: str = ""
    category: str = "general"
    source: ToolSource = ToolSource.LOCAL
    priority: int = 0
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    lazy_load: bool = False
    mcp_server: Optional[str] = None
    dangerous: bool = False
    requires_auth: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "source": self.source.value,
            "priority": self.priority,
            "tags": self.tags,
            "lazy_load": self.lazy_load,
            "mcp_server": self.mcp_server,
            "dangerous": self.dangerous,
        }


@dataclass
class ToolEntry:
    """工具注册条目"""
    metadata: ToolMetadata
    tool: Optional[BaseTool] = None
    loader: Optional[Callable[[], Awaitable[BaseTool]]] = None
    status: ToolStatus = ToolStatus.REGISTERED
    error_message: Optional[str] = None
    load_time: Optional[float] = None

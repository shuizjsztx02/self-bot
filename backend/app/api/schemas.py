from pydantic import BaseModel
from typing import Any, Optional


class MessageCreate(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    stream: bool = False


class ChatResponse(BaseModel):
    conversation_id: str
    response: str
    tool_calls: Optional[list[dict]] = None


class ConversationCreate(BaseModel):
    title: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    system_prompt: Optional[str] = None


class ProviderInfo(BaseModel):
    name: str
    model: str
    available: bool


class SettingsResponse(BaseModel):
    default_provider: str
    providers: list[ProviderInfo]


class SkillExecuteRequest(BaseModel):
    skill_name: str
    parameters: dict[str, Any] = {}


class SkillCreateRequest(BaseModel):
    name: str
    description: str
    prompt_template: str
    parameters: Optional[list[dict]] = None
    required_tools: Optional[list[str]] = None


class MemoryCreateRequest(BaseModel):
    content: str
    memory_type: str = "long_term"
    key: Optional[str] = None
    importance: int = 5


class MemorySearchRequest(BaseModel):
    query: str
    limit: int = 10
    memory_type: Optional[str] = None

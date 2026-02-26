from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from .models import KBRole, DocumentStatus


class KBRoleEnum(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)
    department: Optional[str] = None
    level: int = Field(default=1, ge=1, le=10)


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    department: Optional[str]
    level: int
    is_active: bool
    is_superuser: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=6, max_length=100)
    new_password: str = Field(..., min_length=6, max_length=100)


class RefreshTokenBody(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    parent_id: Optional[str] = None


class UserGroupResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    parent_id: Optional[str]
    member_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    embedding_model: str = Field(default="BAAI/bge-base-zh-v1.5")
    chunk_size: int = Field(default=500, ge=100, le=2000)
    chunk_overlap: int = Field(default=50, ge=0, le=500)
    department: Optional[str] = None
    security_level: int = Field(default=1, ge=1, le=5)


class KnowledgeBaseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    embedding_model: Optional[str] = None
    chunk_size: Optional[int] = Field(None, ge=100, le=2000)
    chunk_overlap: Optional[int] = Field(None, ge=0, le=500)
    department: Optional[str] = None
    security_level: Optional[int] = Field(None, ge=1, le=5)
    is_active: Optional[bool] = None


class KnowledgeBaseResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    owner_id: str
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    department: Optional[str]
    security_level: int
    document_count: int
    chunk_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KnowledgeBaseStats(BaseModel):
    total_documents: int
    total_chunks: int
    total_tokens: int
    by_file_type: Dict[str, int]
    by_status: Dict[str, int]


class FolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    parent_id: Optional[str] = None
    inherit_permissions: bool = True


class FolderUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    inherit_permissions: Optional[bool] = None


class FolderResponse(BaseModel):
    id: str
    kb_id: str
    parent_id: Optional[str]
    name: str
    path: str
    inherit_permissions: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentUpload(BaseModel):
    kb_id: str
    folder_id: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    source: Optional[str] = None
    tags: List[str] = []


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    author: Optional[str] = Field(None, max_length=200)
    source: Optional[str] = Field(None, max_length=500)
    tags: Optional[List[str]] = None
    folder_id: Optional[str] = None


class DocumentResponse(BaseModel):
    id: str
    kb_id: str
    folder_id: Optional[str]
    filename: str
    file_type: str
    file_size: int
    title: Optional[str]
    author: Optional[str]
    source: Optional[str]
    tags: List[str]
    status: str
    current_version: int
    chunk_count: int
    token_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentVersionResponse(BaseModel):
    id: str
    doc_id: str
    version: int
    file_path: str
    change_summary: Optional[str]
    created_by: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ChunkResponse(BaseModel):
    id: str
    doc_id: str
    chunk_index: int
    content: str
    token_count: int
    page_number: Optional[int]
    section_title: Optional[str]
    chunk_metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    kb_ids: Optional[List[str]] = None
    folder_ids: Optional[List[str]] = None
    top_k: int = Field(default=5, ge=1, le=50)
    use_rerank: bool = True
    filters: Optional[Dict[str, Any]] = None


class SearchResult(BaseModel):
    chunk_id: str
    doc_id: str
    doc_name: str
    kb_id: str
    kb_name: str
    content: str
    score: float
    page_number: Optional[int]
    section_title: Optional[str]
    extra_data: Dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total: int
    kb_searched: List[str]
    search_time_ms: float


class PermissionGrant(BaseModel):
    user_id: Optional[str] = None
    group_id: Optional[str] = None
    role: KBRoleEnum
    folder_id: Optional[str] = None
    expires_at: Optional[datetime] = None


class PermissionResponse(BaseModel):
    id: str
    kb_id: str
    folder_id: Optional[str]
    user_id: Optional[str]
    group_id: Optional[str]
    role: str
    granted_by: Optional[str]
    granted_at: datetime
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True


class AttributeRuleCreate(BaseModel):
    attribute_type: str
    operator: str = "=="
    user_attribute: str
    resource_attribute: Optional[str] = None
    target_value: Optional[str] = None
    role: KBRoleEnum
    priority: int = 0


class AttributeRuleResponse(BaseModel):
    id: str
    kb_id: str
    attribute_type: str
    operator: str
    user_attribute: str
    resource_attribute: Optional[str]
    target_value: Optional[str]
    role: str
    priority: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class OperationLogResponse(BaseModel):
    id: str
    user_id: str
    action: str
    resource_type: str
    resource_id: Optional[str]
    details: Dict[str, Any]
    ip_address: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class RAGContext(BaseModel):
    query: str
    contexts: List[SearchResult]
    has_relevant_info: bool
    confidence: float


class RAGSearchInput(BaseModel):
    query: str = Field(..., description="Search query")
    kb_ids: Optional[List[str]] = Field(None, description="Knowledge base IDs to search")
    top_k: int = Field(default=5, description="Number of results to return")


class HybridSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="搜索查询")
    kb_id: str = Field(..., description="知识库ID")
    top_k: int = Field(default=5, ge=1, le=50, description="返回结果数量")
    alpha: float = Field(default=0.5, ge=0.0, le=1.0, description="向量检索权重(0-1)")
    use_rerank: bool = Field(default=False, description="是否使用重排序")


class CrossHybridSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="搜索查询")
    kb_ids: Optional[List[str]] = Field(default=None, description="知识库ID列表，为空则搜索所有")
    top_k: int = Field(default=5, ge=1, le=50, description="返回结果数量")
    alpha: float = Field(default=0.5, ge=0.0, le=1.0, description="向量检索权重(0-1)")
    use_rerank: bool = Field(default=True, description="是否使用重排序")


class AttributionSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="原始查询")
    kb_id: str = Field(..., description="知识库ID")
    answer: str = Field(..., min_length=1, description="LLM生成的回答")
    top_k: int = Field(default=5, ge=1, le=50, description="返回结果数量")
    use_rerank: bool = Field(default=True, description="是否使用重排序")
    rewritten_query: Optional[str] = Field(None, description="重写后的查询")


class SourceReference(BaseModel):
    chunk_id: str
    doc_id: str
    doc_name: str
    content: str
    score: float
    relevance: float = Field(default=0.0, description="相关性评分")
    citation: str = Field(default="", description="引用格式")


class RAGResponse(BaseModel):
    query: str
    answer: str
    sources: List[SourceReference]
    overall_confidence: float = Field(default=0.0, description="整体置信度")
    rewritten_query: Optional[str] = None
    search_time_ms: float = Field(default=0.0)


class CompressedDocumentResponse(BaseModel):
    id: str
    original_content: str
    compressed_content: str
    relevance_score: float
    token_count: int


class CompressionSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="搜索查询")
    kb_id: str = Field(..., description="知识库ID")
    top_k: int = Field(default=10, ge=1, le=50, description="初始检索数量")
    max_tokens: int = Field(default=4000, ge=100, le=16000, description="最大Token数")
    use_hybrid: bool = Field(default=False, description="是否使用混合检索")


class CompressionSearchResponse(BaseModel):
    query: str
    compressed_context: str
    documents: List[CompressedDocumentResponse]
    total_original_tokens: int
    total_compressed_tokens: int
    compression_ratio: float

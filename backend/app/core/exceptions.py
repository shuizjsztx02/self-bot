"""
统一异常处理模块

提供项目级别的异常类层次结构，用于：
1. 统一错误分类
2. 结构化错误信息
3. 便于错误追踪和调试
"""
from typing import Optional, Dict, Any
from enum import Enum


class ErrorCategory(str, Enum):
    """错误类别"""
    EMBEDDING = "embedding"
    RETRIEVAL = "retrieval"
    PARSING = "parsing"
    STORAGE = "storage"
    LLM = "llm"
    MCP = "mcp"
    VALIDATION = "validation"
    PERMISSION = "permission"
    SYSTEM = "system"


class BaseError(Exception):
    """
    基础异常类
    
    所有项目异常的基类，提供统一的错误信息结构
    """
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        self.message = message
        self.category = category
        self.details = details or {}
        self.cause = cause
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            "error": self.__class__.__name__,
            "message": self.message,
            "category": self.category.value,
            "details": self.details,
        }
        if self.cause:
            result["cause"] = str(self.cause)
        return result
    
    def __str__(self) -> str:
        return f"[{self.category.value}] {self.message}"


class EmbeddingError(BaseError):
    """Embedding 相关错误"""
    
    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        details = details or {}
        if model_name:
            details["model_name"] = model_name
        super().__init__(
            message=message,
            category=ErrorCategory.EMBEDDING,
            details=details,
            cause=cause,
        )


class RetrievalError(BaseError):
    """检索相关错误"""
    
    def __init__(
        self,
        message: str,
        kb_id: Optional[str] = None,
        query: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        details = details or {}
        if kb_id:
            details["kb_id"] = kb_id
        if query:
            details["query"] = query[:100]
        super().__init__(
            message=message,
            category=ErrorCategory.RETRIEVAL,
            details=details,
            cause=cause,
        )


class ParsingError(BaseError):
    """文档解析相关错误"""
    
    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        file_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        details = details or {}
        if file_path:
            details["file_path"] = file_path
        if file_type:
            details["file_type"] = file_type
        super().__init__(
            message=message,
            category=ErrorCategory.PARSING,
            details=details,
            cause=cause,
        )


class StorageError(BaseError):
    """存储相关错误"""
    
    def __init__(
        self,
        message: str,
        storage_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        details = details or {}
        if storage_type:
            details["storage_type"] = storage_type
        super().__init__(
            message=message,
            category=ErrorCategory.STORAGE,
            details=details,
            cause=cause,
        )


class LLMError(BaseError):
    """LLM 相关错误"""
    
    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        details = details or {}
        if provider:
            details["provider"] = provider
        if model:
            details["model"] = model
        super().__init__(
            message=message,
            category=ErrorCategory.LLM,
            details=details,
            cause=cause,
        )


class MCPError(BaseError):
    """MCP 工具相关错误"""
    
    def __init__(
        self,
        message: str,
        tool_name: Optional[str] = None,
        server_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        details = details or {}
        if tool_name:
            details["tool_name"] = tool_name
        if server_name:
            details["server_name"] = server_name
        super().__init__(
            message=message,
            category=ErrorCategory.MCP,
            details=details,
            cause=cause,
        )


class ValidationError(BaseError):
    """验证相关错误"""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        details = details or {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)[:100]
        super().__init__(
            message=message,
            category=ErrorCategory.VALIDATION,
            details=details,
            cause=cause,
        )


class PermissionError(BaseError):
    """权限相关错误"""
    
    def __init__(
        self,
        message: str,
        user_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        required_role: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        details = details or {}
        if user_id:
            details["user_id"] = user_id
        if resource_id:
            details["resource_id"] = resource_id
        if required_role:
            details["required_role"] = required_role
        super().__init__(
            message=message,
            category=ErrorCategory.PERMISSION,
            details=details,
            cause=cause,
        )


class ConfigurationError(BaseError):
    """配置相关错误"""
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        details = details or {}
        if config_key:
            details["config_key"] = config_key
        super().__init__(
            message=message,
            category=ErrorCategory.SYSTEM,
            details=details,
            cause=cause,
        )


class ResourceNotFoundError(BaseError):
    """资源未找到错误"""
    
    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        details = details or {}
        details["resource_type"] = resource_type
        details["resource_id"] = resource_id
        super().__init__(
            message=f"{resource_type} with id '{resource_id}' not found",
            category=ErrorCategory.SYSTEM,
            details=details,
        )


class RateLimitError(BaseError):
    """速率限制错误"""
    
    def __init__(
        self,
        message: str,
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        details = details or {}
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(
            message=message,
            category=ErrorCategory.SYSTEM,
            details=details,
            cause=cause,
        )

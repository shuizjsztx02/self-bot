"""
阶段三优化功能测试

测试内容：
1. 异常类 - 统一异常处理
2. 日志配置 - 日志系统
3. 错误处理装饰器
"""
import pytest
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestExceptions:
    """异常类测试"""
    
    def test_base_error(self):
        """测试基础异常"""
        from app.core.exceptions import BaseError, ErrorCategory
        
        error = BaseError(
            message="测试错误",
            category=ErrorCategory.SYSTEM,
            details={"key": "value"},
        )
        
        assert error.message == "测试错误"
        assert error.category == ErrorCategory.SYSTEM
        assert error.details == {"key": "value"}
        
        error_dict = error.to_dict()
        assert error_dict["error"] == "BaseError"
        assert error_dict["category"] == "system"
    
    def test_embedding_error(self):
        """测试 Embedding 错误"""
        from app.core.exceptions import EmbeddingError
        
        error = EmbeddingError(
            message="模型加载失败",
            model_name="test-model",
        )
        
        assert error.details["model_name"] == "test-model"
        assert "模型加载失败" in str(error)
    
    def test_retrieval_error(self):
        """测试检索错误"""
        from app.core.exceptions import RetrievalError
        
        error = RetrievalError(
            message="检索失败",
            kb_id="kb-123",
            query="测试查询",
        )
        
        assert error.details["kb_id"] == "kb-123"
        assert "测试查询" in error.details["query"]
    
    def test_parsing_error(self):
        """测试解析错误"""
        from app.core.exceptions import ParsingError
        
        error = ParsingError(
            message="解析失败",
            file_path="/path/to/file.pdf",
            file_type="pdf",
        )
        
        assert error.details["file_path"] == "/path/to/file.pdf"
        assert error.details["file_type"] == "pdf"
    
    def test_llm_error(self):
        """测试 LLM 错误"""
        from app.core.exceptions import LLMError
        
        error = LLMError(
            message="API 调用失败",
            provider="openai",
            model="gpt-4",
        )
        
        assert error.details["provider"] == "openai"
        assert error.details["model"] == "gpt-4"
    
    def test_mcp_error(self):
        """测试 MCP 错误"""
        from app.core.exceptions import MCPError
        
        error = MCPError(
            message="工具执行失败",
            tool_name="test_tool",
            server_name="test_server",
        )
        
        assert error.details["tool_name"] == "test_tool"
        assert error.details["server_name"] == "test_server"
    
    def test_validation_error(self):
        """测试验证错误"""
        from app.core.exceptions import ValidationError
        
        error = ValidationError(
            message="字段验证失败",
            field="name",
            value="invalid",
        )
        
        assert error.details["field"] == "name"
        assert "invalid" in error.details["value"]
    
    def test_permission_error(self):
        """测试权限错误"""
        from app.core.exceptions import PermissionError
        
        error = PermissionError(
            message="权限不足",
            user_id="user-123",
            resource_id="res-456",
            required_role="admin",
        )
        
        assert error.details["user_id"] == "user-123"
        assert error.details["required_role"] == "admin"
    
    def test_resource_not_found_error(self):
        """测试资源未找到错误"""
        from app.core.exceptions import ResourceNotFoundError
        
        error = ResourceNotFoundError(
            resource_type="KnowledgeBase",
            resource_id="kb-123",
        )
        
        assert "KnowledgeBase" in str(error)
        assert "kb-123" in str(error)
    
    def test_configuration_error(self):
        """测试配置错误"""
        from app.core.exceptions import ConfigurationError
        
        error = ConfigurationError(
            message="缺少必要配置",
            config_key="API_KEY",
        )
        
        assert error.details["config_key"] == "API_KEY"
    
    def test_rate_limit_error(self):
        """测试速率限制错误"""
        from app.core.exceptions import RateLimitError
        
        error = RateLimitError(
            message="请求过于频繁",
            retry_after=60,
        )
        
        assert error.details["retry_after"] == 60
    
    def test_error_str_representation(self):
        """测试错误字符串表示"""
        from app.core.exceptions import BaseError, ErrorCategory
        
        error = BaseError(
            message="测试消息",
            category=ErrorCategory.EMBEDDING,
        )
        
        error_str = str(error)
        assert "[embedding]" in error_str
        assert "测试消息" in error_str
    
    def test_error_with_cause(self):
        """测试带原因的异常"""
        from app.core.exceptions import BaseError, ErrorCategory
        
        original_error = ValueError("原始错误")
        error = BaseError(
            message="包装错误",
            category=ErrorCategory.SYSTEM,
            cause=original_error,
        )
        
        assert error.cause == original_error
        error_dict = error.to_dict()
        assert "原始错误" in error_dict["cause"]


class TestErrorCategory:
    """错误类别枚举测试"""
    
    def test_category_values(self):
        """测试错误类别值"""
        from app.core.exceptions import ErrorCategory
        
        assert ErrorCategory.EMBEDDING.value == "embedding"
        assert ErrorCategory.RETRIEVAL.value == "retrieval"
        assert ErrorCategory.PARSING.value == "parsing"
        assert ErrorCategory.STORAGE.value == "storage"
        assert ErrorCategory.LLM.value == "llm"
        assert ErrorCategory.MCP.value == "mcp"
        assert ErrorCategory.VALIDATION.value == "validation"
        assert ErrorCategory.PERMISSION.value == "permission"
        assert ErrorCategory.SYSTEM.value == "system"


class TestLoggingConfig:
    """日志配置测试"""
    
    def test_get_logger(self):
        """测试获取日志器"""
        from app.core.logging_config import get_logger
        
        logger = get_logger("test_module")
        
        assert logger.name == "test_module"
        assert isinstance(logger, logging.Logger)
    
    def test_operation_logger_success(self):
        """测试操作日志记录器 - 成功场景"""
        from app.core.logging_config import OperationLogger
        
        logger = logging.getLogger("test")
        
        with OperationLogger(logger, "测试操作") as op:
            pass
    
    def test_operation_logger_failure(self):
        """测试操作日志记录器 - 失败场景"""
        from app.core.logging_config import OperationLogger
        
        logger = logging.getLogger("test")
        
        with pytest.raises(ValueError):
            with OperationLogger(logger, "失败操作") as op:
                raise ValueError("测试异常")
    
    def test_log_function_call_decorator(self):
        """测试函数调用日志装饰器"""
        from app.core.logging_config import log_function_call
        
        logger = logging.getLogger("test")
        
        @log_function_call(logger)
        def test_func(a, b):
            return a + b
        
        result = test_func(1, 2)
        
        assert result == 3
    
    def test_log_function_call_decorator_with_exception(self):
        """测试函数调用日志装饰器 - 异常场景"""
        from app.core.logging_config import log_function_call
        
        logger = logging.getLogger("test")
        
        @log_function_call(logger)
        def test_func():
            raise ValueError("测试异常")
        
        with pytest.raises(ValueError):
            test_func()
    
    @pytest.mark.asyncio
    async def test_log_async_function_call_decorator(self):
        """测试异步函数调用日志装饰器"""
        from app.core.logging_config import log_async_function_call
        
        logger = logging.getLogger("test")
        
        @log_async_function_call(logger)
        async def test_async_func(a, b):
            return a + b
        
        result = await test_async_func(1, 2)
        
        assert result == 3


class TestColorFormatter:
    """彩色格式化器测试"""
    
    def test_color_formatter(self):
        """测试彩色格式化"""
        from app.core.logging_config import ColorFormatter
        
        formatter = ColorFormatter("%(levelname)s - %(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="测试消息",
            args=(),
            exc_info=None,
        )
        
        formatted = formatter.format(record)
        
        assert "INFO" in formatted
        assert "测试消息" in formatted


def run_tests():
    """运行所有测试"""
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_tests()

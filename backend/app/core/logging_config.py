"""
日志配置模块

提供统一的日志配置和格式化
"""
import logging
import sys
from typing import Optional
from pathlib import Path
from datetime import datetime
import functools


LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class ColorFormatter(logging.Formatter):
    """彩色日志格式化器"""
    
    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, "")
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    use_color: bool = True,
) -> None:
    """
    配置日志系统
    
    Args:
        level: 日志级别
        log_file: 日志文件路径
        use_color: 是否使用彩色输出
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    handlers = []
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    
    if use_color and sys.stdout.isatty():
        formatter = ColorFormatter(LOG_FORMAT, DATE_FORMAT)
    else:
        formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)
    
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        handlers.append(file_handler)
    
    root_logger.handlers = handlers


class OperationLogger:
    """
    操作日志记录器
    
    用于记录长时间操作的开始、结束和耗时
    """
    
    def __init__(self, logger: logging.Logger, operation: str, level: int = logging.INFO):
        self.logger = logger
        self.operation = operation
        self.level = level
        self.start_time: Optional[float] = None
    
    def __enter__(self):
        self.start_time = datetime.now().timestamp()
        self.logger.log(self.level, f"开始: {self.operation}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = datetime.now().timestamp() - self.start_time
        if exc_type:
            self.logger.error(
                f"失败: {self.operation} (耗时: {elapsed:.2f}s) - {exc_val}"
            )
        else:
            self.logger.log(
                self.level,
                f"完成: {self.operation} (耗时: {elapsed:.2f}s)"
            )
        return False


def log_function_call(logger: logging.Logger):
    """函数调用日志装饰器"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger.debug(f"调用: {func.__name__}(args={len(args)}, kwargs={list(kwargs.keys())})")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"返回: {func.__name__} -> {type(result).__name__}")
                return result
            except Exception as e:
                logger.error(f"异常: {func.__name__} -> {e}")
                raise
        return wrapper
    return decorator


def log_async_function_call(logger: logging.Logger):
    """异步函数调用日志装饰器"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            logger.debug(f"调用: {func.__name__}(args={len(args)}, kwargs={list(kwargs.keys())})")
            try:
                result = await func(*args, **kwargs)
                logger.debug(f"返回: {func.__name__} -> {type(result).__name__}")
                return result
            except Exception as e:
                logger.error(f"异常: {func.__name__} -> {e}")
                raise
        return wrapper
    return decorator


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志器"""
    return logging.getLogger(name)

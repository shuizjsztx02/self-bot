from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ParsedDocument(BaseModel):
    content: str
    doc_metadata: Dict[str, Any] = Field(default_factory=dict)
    pages: Optional[List[Dict]] = None
    sections: Optional[List[Dict]] = None
    tables: Optional[List[Dict]] = None
    images: Optional[List[Dict]] = None


class ChunkResult(BaseModel):
    content: str
    token_count: int
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    chunk_metadata: Dict[str, Any] = Field(default_factory=dict)


class TokenCounter:
    """
    Token 计数器
    
    使用 tiktoken 进行精确的 token 计数
    支持多种编码方式
    """
    
    _instance = None
    _encoders: Dict[str, Any] = {}
    
    ENCODING_MAP = {
        "gpt-4": "cl100k_base",
        "gpt-4o": "cl100k_base",
        "gpt-3.5-turbo": "cl100k_base",
        "text-embedding-ada-002": "cl100k_base",
        "default": "cl100k_base",
    }
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_encoder(self, model: str = "default"):
        """获取指定模型的编码器"""
        encoding_name = self.ENCODING_MAP.get(model, self.ENCODING_MAP["default"])
        
        if encoding_name not in self._encoders:
            try:
                import tiktoken
                self._encoders[encoding_name] = tiktoken.get_encoding(encoding_name)
                logger.debug(f"Loaded tiktoken encoder: {encoding_name}")
            except ImportError:
                logger.warning(
                    "tiktoken not installed, falling back to character-based estimation. "
                    "Install with: pip install tiktoken"
                )
                self._encoders[encoding_name] = None
            except Exception as e:
                logger.warning(f"Failed to load tiktoken encoder: {e}")
                self._encoders[encoding_name] = None
        
        return self._encoders[encoding_name]
    
    def count_tokens(self, text: str, model: str = "default") -> int:
        """
        计算文本的 token 数量
        
        Args:
            text: 要计算的文本
            model: 模型名称，用于选择编码器
        
        Returns:
            token 数量
        """
        if not text:
            return 0
        
        encoder = self.get_encoder(model)
        
        if encoder is not None:
            return len(encoder.encode(text))
        
        return self._estimate_tokens(text)
    
    def _estimate_tokens(self, text: str) -> int:
        """
        基于字符的 token 估算（fallback）
        
        规则：
        - 中文字符：约 1.5 字/token
        - 英文字符：约 4 字符/token
        - 混合文本：加权平均
        """
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        total_chars = len(text)
        non_chinese = total_chars - chinese_chars
        
        estimated = int(chinese_chars / 1.5 + non_chinese / 4)
        
        return max(estimated, 1)
    
    def count_tokens_batch(self, texts: List[str], model: str = "default") -> List[int]:
        """批量计算 token 数量"""
        return [self.count_tokens(text, model) for text in texts]


_token_counter = TokenCounter()


class DocumentParser(ABC):
    
    def __init__(self, token_model: str = "default"):
        self.token_model = token_model
        self._token_counter = _token_counter
    
    @abstractmethod
    async def parse(self, file_path: str) -> ParsedDocument:
        pass
    
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        pass
    
    def count_tokens(self, text: str) -> int:
        """
        计算文本的 token 数量
        
        使用 tiktoken 进行精确计数，如果不可用则使用估算
        """
        return self._token_counter.count_tokens(text, self.token_model)
    
    def chunk_text(
        self,
        text: str,
        chunk_size: int = 500,
        overlap: int = 50,
    ) -> List[str]:
        if not text:
            return []
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            if end < len(text):
                for i in range(end, max(end - 100, start), -1):
                    if text[i] in ['\n', '.', '!', '?', '。', '！', '？']:
                        end = i + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap if end < len(text) else end
        
        return chunks

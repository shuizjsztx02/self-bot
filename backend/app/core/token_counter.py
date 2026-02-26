"""
Token计数器

提供统一的Token计数功能
"""
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class TokenCounter:
    """
    Token计数器
    
    支持多种模型的Token计数
    """
    
    _encoders = {}
    
    def __init__(self, model: str = "gpt-4"):
        self.model = model
        self._encoder = None
    
    def _get_encoder(self):
        """获取编码器"""
        if self._encoder is not None:
            return self._encoder
        
        try:
            import tiktoken
            
            model_mapping = {
                "gpt-4": "cl100k_base",
                "gpt-4o": "cl100k_base",
                "gpt-3.5-turbo": "cl100k_base",
                "text-embedding-ada-002": "cl100k_base",
            }
            
            encoding_name = model_mapping.get(self.model, "cl100k_base")
            
            if encoding_name not in self._encoders:
                self._encoders[encoding_name] = tiktoken.get_encoding(encoding_name)
            
            self._encoder = self._encoders[encoding_name]
            return self._encoder
            
        except ImportError:
            logger.warning("tiktoken not installed, using approximate token count")
            return None
    
    def count_tokens(self, text: str) -> int:
        """
        计算文本的Token数量
        
        Args:
            text: 输入文本
        
        Returns:
            Token数量
        """
        if not text:
            return 0
        
        encoder = self._get_encoder()
        
        if encoder is not None:
            return len(encoder.encode(text))
        
        return len(text) // 4
    
    def count_tokens_batch(self, texts: List[str]) -> List[int]:
        """
        批量计算Token数量
        
        Args:
            texts: 文本列表
        
        Returns:
            Token数量列表
        """
        return [self.count_tokens(text) for text in texts]
    
    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """
        将文本截断到指定Token数量
        
        Args:
            text: 输入文本
            max_tokens: 最大Token数量
        
        Returns:
            截断后的文本
        """
        if not text:
            return text
        
        encoder = self._get_encoder()
        
        if encoder is not None:
            tokens = encoder.encode(text)
            if len(tokens) <= max_tokens:
                return text
            return encoder.decode(tokens[:max_tokens])
        
        approx_chars = max_tokens * 4
        return text[:approx_chars]
    
    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: Optional[str] = None,
    ) -> float:
        """
        估算API调用成本
        
        Args:
            input_tokens: 输入Token数量
            output_tokens: 输出Token数量
            model: 模型名称
        
        Returns:
            估算成本（美元）
        """
        model = model or self.model
        
        pricing = {
            "gpt-4": {"input": 0.03 / 1000, "output": 0.06 / 1000},
            "gpt-4o": {"input": 0.005 / 1000, "output": 0.015 / 1000},
            "gpt-3.5-turbo": {"input": 0.0005 / 1000, "output": 0.0015 / 1000},
        }
        
        rates = pricing.get(model, {"input": 0.01 / 1000, "output": 0.03 / 1000})
        
        return (input_tokens * rates["input"]) + (output_tokens * rates["output"])


_token_counter_instance: Optional[TokenCounter] = None


def get_token_counter(model: str = "gpt-4") -> TokenCounter:
    """获取Token计数器实例"""
    global _token_counter_instance
    
    if _token_counter_instance is None:
        _token_counter_instance = TokenCounter(model)
    
    return _token_counter_instance

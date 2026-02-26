from typing import List, Optional
from collections import OrderedDict
import asyncio

from app.config import settings


class LRUCache:
    """LRU 缓存实现"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: OrderedDict = OrderedDict()
    
    def get(self, key: str) -> Optional[List[float]]:
        if key not in self._cache:
            return None
        self._cache.move_to_end(key)
        return self._cache[key]
    
    def set(self, key: str, value: List[float]) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
        self._cache[key] = value
    
    def clear(self) -> None:
        self._cache.clear()
    
    def __len__(self) -> int:
        return len(self._cache)
    
    def __contains__(self, key: str) -> bool:
        return key in self._cache


class EmbeddingService:
    
    def __init__(
        self,
        model_name: str = None,
        cache_enabled: bool = True,
        cache_max_size: int = 1000,
    ):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.cache_enabled = cache_enabled
        self.cache_max_size = cache_max_size
        self._model = None
        self._cache = LRUCache(max_size=cache_max_size) if cache_enabled else None
    
    @property
    def model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(
                    self.model_name,
                    trust_remote_code=True,
                )
            except ImportError:
                raise ImportError("sentence-transformers not installed. Run: pip install sentence-transformers")
        return self._model
    
    def _get_cache_key(self, text: str) -> str:
        import hashlib
        return hashlib.md5(f"{self.model_name}:{text}".encode()).hexdigest()
    
    async def embed_text(self, text: str) -> List[float]:
        if self.cache_enabled and self._cache is not None:
            cache_key = self._get_cache_key(text)
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
        
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None,
            self._embed_sync,
            text,
        )
        
        if self.cache_enabled and self._cache is not None:
            self._cache.set(cache_key, embedding)
        
        return embedding
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        
        uncached_texts = []
        uncached_indices = []
        results = [None] * len(texts)
        
        if self.cache_enabled and self._cache is not None:
            for i, text in enumerate(texts):
                cache_key = self._get_cache_key(text)
                cached = self._cache.get(cache_key)
                if cached is not None:
                    results[i] = cached
                else:
                    uncached_texts.append(text)
                    uncached_indices.append(i)
        else:
            uncached_texts = texts
            uncached_indices = list(range(len(texts)))
        
        if uncached_texts:
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,
                self._embed_batch_sync,
                uncached_texts,
            )
            
            for idx, embedding in zip(uncached_indices, embeddings):
                results[idx] = embedding
                
                if self.cache_enabled and self._cache is not None:
                    cache_key = self._get_cache_key(texts[idx])
                    self._cache.set(cache_key, embedding)
        
        return results
    
    def _embed_sync(self, text: str) -> List[float]:
        return self.model.encode(text).tolist()
    
    def _embed_batch_sync(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(texts)
        return embeddings.tolist()
    
    def clear_cache(self):
        if self._cache is not None:
            self._cache.clear()
    
    def get_cache_size(self) -> int:
        """获取当前缓存大小"""
        return len(self._cache) if self._cache is not None else 0
    
    def get_embedding_dim(self) -> int:
        if "bge-base" in self.model_name:
            return 768
        elif "bge-large" in self.model_name:
            return 1024
        elif "bge-small" in self.model_name:
            return 384
        return 768

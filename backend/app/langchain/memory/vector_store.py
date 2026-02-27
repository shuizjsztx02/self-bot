"""
向量存储实现

支持后端：
1. ChromaDB - 持久化向量数据库（主要）
2. InMemoryVectorStore - 内存存储（fallback）
"""
from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field
from pathlib import Path
import logging
import math

logger = logging.getLogger(__name__)


class VectorDocument(BaseModel):
    """向量文档模型"""
    id: str
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class InMemoryVectorStore:
    """
    内存向量存储
    
    使用余弦相似度进行搜索，作为 ChromaDB 的 fallback 方案
    """
    
    def __init__(self, embedding_dim: int = 768):
        self.embedding_dim = embedding_dim
        self._store: Dict[str, Dict[str, Any]] = {}
    
    async def insert(
        self,
        documents: List[VectorDocument],
        embeddings: List[List[float]],
    ) -> List[str]:
        """插入文档"""
        ids = []
        for doc, emb in zip(documents, embeddings):
            doc.embedding = emb
            self._store[doc.id] = {
                "document": doc,
                "embedding": emb,
            }
            ids.append(doc.id)
        return ids
    
    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        filter_dict: Optional[Dict] = None,
    ) -> List[Tuple[VectorDocument, float]]:
        """搜索文档"""
        if not self._store:
            return []
        
        results = []
        
        for doc_id, data in self._store.items():
            doc = data["document"]
            stored_emb = data["embedding"]
            
            if filter_dict:
                match = True
                for key, value in filter_dict.items():
                    if doc.metadata.get(key) != value:
                        match = False
                        break
                if not match:
                    continue
            
            similarity = self._cosine_similarity(query_embedding, stored_emb)
            results.append((doc, similarity))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        
        if norm_a == 0 or norm_b == 0:
            return 0
        
        return dot_product / (norm_a * norm_b)
    
    async def delete(self, ids: List[str]) -> None:
        """删除文档"""
        for id_ in ids:
            self._store.pop(id_, None)
    
    async def count(self) -> int:
        """返回文档数量"""
        return len(self._store)
    
    async def clear(self) -> None:
        """清空存储"""
        self._store.clear()


class ChromaVectorStore:
    """
    ChromaDB 向量存储
    
    持久化存储，支持高效的向量检索
    当 ChromaDB 不可用时，自动 fallback 到内存存储
    """
    
    def __init__(
        self,
        collection_name: str = "memory_store",
        persist_directory: str = None,
        embedding_dim: int = 768,
    ):
        from app.config import settings
        self.collection_name = collection_name
        self.persist_directory = persist_directory or settings.AGENT_VECTOR_PATH
        self.embedding_dim = embedding_dim
        self._collection = None
        self._client = None
        self._initialized = False
        self._fallback_store: Optional[InMemoryVectorStore] = None
    
    async def initialize(self) -> None:
        """初始化 ChromaDB"""
        if self._initialized:
            return
        
        try:
            import chromadb
            
            Path(self.persist_directory).mkdir(parents=True, exist_ok=True)
            
            self._client = chromadb.PersistentClient(path=self.persist_directory)
            
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            
            self._initialized = True
            logger.info(f"ChromaDB initialized: {self.persist_directory}/{self.collection_name}")
            
        except ImportError:
            logger.warning(
                "chromadb not installed, using in-memory fallback. "
                "Install with: pip install chromadb"
            )
            self._fallback_store = InMemoryVectorStore(self.embedding_dim)
            self._initialized = True
        except Exception as e:
            logger.warning(f"Chroma initialization failed: {e}, using in-memory fallback")
            self._fallback_store = InMemoryVectorStore(self.embedding_dim)
            self._initialized = True
    
    async def insert(
        self,
        documents: List[VectorDocument],
        embeddings: List[List[float]],
    ) -> List[str]:
        """插入文档"""
        await self.initialize()
        
        ids = [doc.id for doc in documents]
        
        if self._collection:
            metadatas = []
            for doc in documents:
                meta = doc.metadata.copy()
                meta["content"] = doc.content
                metadatas.append(meta)
            
            self._collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=[doc.content for doc in documents],
            )
        elif self._fallback_store:
            await self._fallback_store.insert(documents, embeddings)
        
        return ids
    
    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_dict: Optional[Dict] = None,
    ) -> List[Tuple[VectorDocument, float]]:
        """搜索文档"""
        await self.initialize()
        
        results = []
        
        if self._collection:
            where = None
            if filter_dict:
                where = filter_dict
            
            search_results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
            
            if search_results and search_results["ids"]:
                for i, doc_id in enumerate(search_results["ids"][0]):
                    content = search_results["documents"][0][i] if search_results["documents"] else ""
                    metadata = search_results["metadatas"][0][i] if search_results["metadatas"] else {}
                    distance = search_results["distances"][0][i] if search_results["distances"] else 0
                    
                    metadata.pop("content", None)
                    
                    doc = VectorDocument(
                        id=doc_id,
                        content=content,
                        metadata=metadata,
                    )
                    results.append((doc, 1 - distance))
        elif self._fallback_store:
            results = await self._fallback_store.search(query_embedding, top_k, filter_dict)
        
        return results
    
    async def delete(self, ids: List[str]) -> None:
        """删除文档"""
        await self.initialize()
        
        if self._collection:
            self._collection.delete(ids=ids)
        elif self._fallback_store:
            await self._fallback_store.delete(ids)
    
    async def count(self) -> int:
        """返回文档数量"""
        await self.initialize()
        
        if self._collection:
            return self._collection.count()
        elif self._fallback_store:
            return await self._fallback_store.count()
        return 0
    
    async def clear(self) -> None:
        """清空存储"""
        await self.initialize()
        
        if self._client and self._collection:
            self._client.delete_collection(self.collection_name)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        elif self._fallback_store:
            await self._fallback_store.clear()

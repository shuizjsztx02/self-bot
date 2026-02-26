from typing import List, Optional, Tuple
from pydantic import BaseModel
import asyncio
import logging

logger = logging.getLogger(__name__)


class EmbeddingModelError(Exception):
    """Embedding 模型相关错误"""
    pass


class RAGConfig(BaseModel):
    embedding_model: str = "BAAI/bge-base-zh-v1.5"
    reranker_model: str = "BAAI/bge-reranker-base"
    embedding_dim: int = 768
    top_k: int = 5
    rerank_top_n: int = 3
    require_embedding_model: bool = True


class RAGRetriever:
    def __init__(
        self,
        vector_store,
        config: Optional[RAGConfig] = None,
    ):
        self.vector_store = vector_store
        self.config = config or RAGConfig()
        self._embedding_model = None
        self._reranker = None
        self._embedding_dim: Optional[int] = None
        
        if self.config.require_embedding_model:
            self._ensure_embedding_model()
    
    def _ensure_embedding_model(self) -> None:
        """确保 Embedding 模型可用"""
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {self.config.embedding_model}")
            self._embedding_model = SentenceTransformer(
                self.config.embedding_model,
                trust_remote_code=True,
            )
            self._embedding_dim = self._embedding_model.get_sentence_embedding_dimension()
            logger.info(f"Embedding model loaded, dimension: {self._embedding_dim}")
        except ImportError as e:
            raise EmbeddingModelError(
                "sentence-transformers is required for embedding. "
                "Install with: pip install sentence-transformers"
            ) from e
        except Exception as e:
            raise EmbeddingModelError(
                f"Failed to load embedding model '{self.config.embedding_model}': {e}"
            ) from e
    
    @property
    def embedding_model(self):
        if self._embedding_model is None:
            self._ensure_embedding_model()
        return self._embedding_model
    
    @property
    def embedding_dim(self) -> int:
        """获取实际的 embedding 维度"""
        if self._embedding_dim is None:
            self._ensure_embedding_model()
        return self._embedding_dim
    
    @property
    def reranker(self):
        if self._reranker is None:
            try:
                from sentence_transformers import CrossEncoder
                logger.info(f"Loading reranker model: {self.config.reranker_model}")
                self._reranker = CrossEncoder(
                    self.config.reranker_model,
                    trust_remote_code=True,
                )
                logger.info("Reranker model loaded successfully")
            except ImportError:
                logger.warning(
                    "sentence-transformers not installed for reranker, "
                    "reranking will be disabled"
                )
            except Exception as e:
                logger.warning(f"Failed to load reranker model: {e}")
        return self._reranker
    
    def _get_embedding(self, text: str) -> List[float]:
        """生成单个文本的 embedding"""
        if self.embedding_model is None:
            raise EmbeddingModelError("Embedding model not available")
        return self.embedding_model.encode(text).tolist()
    
    async def embed_text(self, text: str) -> List[float]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_embedding, text)
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if self.embedding_model is None:
            raise EmbeddingModelError("Embedding model not available")
        
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            self.embedding_model.encode,
            texts,
        )
        return embeddings.tolist()
    
    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        use_rerank: bool = True,
    ) -> List[Tuple[str, float, dict]]:
        top_k = top_k or self.config.top_k
        
        query_embedding = await self.embed_text(query)
        
        results = await self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k * 2 if use_rerank else top_k,
        )
        
        if not results:
            return []
        
        if use_rerank and self.reranker:
            results = await self._rerank(query, results)
        
        return [
            (doc.content, score, doc.metadata)
            for doc, score in results[:top_k]
        ]
    
    async def _rerank(
        self,
        query: str,
        results: List[Tuple],
    ) -> List[Tuple]:
        if not self.reranker:
            return results
        
        loop = asyncio.get_event_loop()
        
        pairs = [(query, doc.content) for doc, _ in results]
        
        scores = await loop.run_in_executor(
            None,
            self.reranker.predict,
            pairs,
        )
        
        reranked = list(zip(results, scores))
        reranked.sort(key=lambda x: x[1], reverse=True)
        
        return [(doc, score) for (doc, _), score in reranked]
    
    async def index_documents(
        self,
        documents: List[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        from .vector_store import VectorDocument
        import uuid
        
        embeddings = await self.embed_texts(documents)
        
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in documents]
        
        if metadatas is None:
            metadatas = [{} for _ in documents]
        
        vector_docs = [
            VectorDocument(
                id=ids[i],
                content=documents[i],
                metadata=metadatas[i],
            )
            for i in range(len(documents))
        ]
        
        return await self.vector_store.insert(vector_docs, embeddings)

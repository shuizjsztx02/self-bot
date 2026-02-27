from typing import List, Optional, Tuple
from pydantic import BaseModel
import asyncio
import logging
import os

from app.config import settings
from app.core.device_utils import get_optimal_device, log_device_status

logger = logging.getLogger(__name__)


def get_local_model_path(model_name: str) -> Optional[str]:
    """
    获取本地模型路径
    
    HuggingFace 缓存目录结构:
    model_hub/
    └── models--BAAI--bge-base-zh-v1.5/
        ├── refs/
        │   └── main  (包含 commit hash)
        └── snapshots/
            └── <commit_hash>/  (实际模型文件)
    """
    model_hub_path = settings.MODEL_HUB_PATH
    if not os.path.exists(model_hub_path):
        return None
    
    model_dir_name = model_name.replace("/", "--")
    model_dir = os.path.join(model_hub_path, f"models--{model_dir_name}")
    
    if not os.path.exists(model_dir):
        return None
    
    refs_file = os.path.join(model_dir, "refs", "main")
    if os.path.exists(refs_file):
        with open(refs_file, "r") as f:
            commit_hash = f.read().strip()
        
        snapshot_path = os.path.join(model_dir, "snapshots", commit_hash)
        if os.path.exists(snapshot_path):
            return snapshot_path
    
    snapshots_dir = os.path.join(model_dir, "snapshots")
    if os.path.exists(snapshots_dir):
        subdirs = [d for d in os.listdir(snapshots_dir) 
                   if os.path.isdir(os.path.join(snapshots_dir, d))]
        if subdirs:
            return os.path.join(snapshots_dir, subdirs[0])
    
    return None


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
        device: Optional[str] = None,
    ):
        self.vector_store = vector_store
        self.config = config or RAGConfig()
        self.device = device or get_optimal_device()
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
            logger.info(f"Using device: {self.device}")
            
            local_path = get_local_model_path(self.config.embedding_model)
            if local_path:
                logger.info(f"Loading from local path: {local_path}")
                self._embedding_model = SentenceTransformer(
                    local_path,
                    trust_remote_code=True,
                    device=self.device,
                )
            else:
                self._embedding_model = SentenceTransformer(
                    self.config.embedding_model,
                    trust_remote_code=True,
                    device=self.device,
                )
            self._embedding_dim = self._embedding_model.get_sentence_embedding_dimension()
            logger.info(f"Embedding model loaded on {self.device}, dimension: {self._embedding_dim}")
        except ImportError as e:
            raise EmbeddingModelError(
                "sentence-transformers is required for embedding. "
                "Install with: pip install sentence-transformers"
            ) from e
        except Exception as e:
            if "cuda" in self.device or self.device == "mps":
                logger.warning(f"Failed to load model on {self.device}, falling back to CPU: {e}")
                self.device = "cpu"
                self._ensure_embedding_model()
                return
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
                logger.info(f"Using device: {self.device}")
                
                local_path = get_local_model_path(self.config.reranker_model)
                if local_path:
                    logger.info(f"Loading reranker from local path: {local_path}")
                    self._reranker = CrossEncoder(
                        local_path,
                        trust_remote_code=True,
                        device=self.device,
                    )
                else:
                    self._reranker = CrossEncoder(
                        self.config.reranker_model,
                        trust_remote_code=True,
                        device=self.device,
                    )
                logger.info(f"Reranker model loaded on {self.device}")
            except ImportError:
                logger.warning(
                    "sentence-transformers not installed for reranker, "
                    "reranking will be disabled"
                )
            except Exception as e:
                if "cuda" in self.device or self.device == "mps":
                    logger.warning(f"Failed to load reranker on {self.device}, falling back to CPU: {e}")
                    self.device = "cpu"
                    self._reranker = None
                    return self.reranker
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

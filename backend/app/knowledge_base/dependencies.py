import logging
import os
from functools import lru_cache
from typing import Optional

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.knowledge_base.vector_store import VectorStoreFactory, VectorStoreBackend
from app.knowledge_base.services.embedding import EmbeddingService
from app.knowledge_base.services.bm25 import BM25Index, BM25Config
from app.knowledge_base.services.document import DocumentService
from app.knowledge_base.services.knowledge_base import KnowledgeBaseService
from app.knowledge_base.services.search import SearchService
from app.knowledge_base.services.permission import PermissionService
from app.config import settings

logger = logging.getLogger(__name__)


class ServiceContainer:
    """服务容器，管理单例服务实例"""
    
    _instance: Optional["ServiceContainer"] = None
    
    def __init__(self):
        self._vector_store: Optional[VectorStoreBackend] = None
        self._embedding_service: Optional[EmbeddingService] = None
        self._bm25_indexes: dict = {}
    
    @classmethod
    def get_instance(cls) -> "ServiceContainer":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @property
    def vector_store(self) -> VectorStoreBackend:
        if self._vector_store is None:
            self._vector_store = VectorStoreFactory.create("chroma")
            logger.info("VectorStore instance created")
        return self._vector_store
    
    @property
    def embedding_service(self) -> EmbeddingService:
        if self._embedding_service is None:
            self._embedding_service = EmbeddingService()
            logger.info("EmbeddingService instance created")
        return self._embedding_service
    
    def get_bm25_index(self, kb_id: str) -> BM25Index:
        if kb_id not in self._bm25_indexes:
            config = BM25Config(k1=1.5, b=0.75, epsilon=0.25)
            index_path = os.path.join(BM25_PERSIST_PATH, f"bm25_{kb_id}.json")
            self._bm25_indexes[kb_id] = BM25Index(
                config=config,
                persist_path=index_path,
            )
            logger.info(f"BM25Index created for kb_id={kb_id}")
        return self._bm25_indexes[kb_id]
    
    def clear_bm25_index(self, kb_id: str) -> None:
        if kb_id in self._bm25_indexes:
            del self._bm25_indexes[kb_id]
            logger.info(f"BM25Index cleared for kb_id={kb_id}")
    
    def clear_all(self) -> None:
        self._vector_store = None
        self._embedding_service = None
        self._bm25_indexes = {}
        logger.info("All service instances cleared")


def get_service_container() -> ServiceContainer:
    return ServiceContainer.get_instance()


def get_vector_store(
    container: ServiceContainer = Depends(get_service_container),
) -> VectorStoreBackend:
    return container.vector_store


def get_embedding_service(
    container: ServiceContainer = Depends(get_service_container),
) -> EmbeddingService:
    return container.embedding_service


def get_document_service(
    db: AsyncSession = Depends(get_async_session),
    vector_store: VectorStoreBackend = Depends(get_vector_store),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> DocumentService:
    return DocumentService(
        db=db,
        vector_store=vector_store,
        embedding_service=embedding_service,
    )


def get_knowledge_base_service(
    db: AsyncSession = Depends(get_async_session),
    vector_store: VectorStoreBackend = Depends(get_vector_store),
) -> KnowledgeBaseService:
    return KnowledgeBaseService(db, vector_store)


def get_search_service(
    vector_store: VectorStoreBackend = Depends(get_vector_store),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> SearchService:
    return SearchService(
        vector_store=vector_store,
        embedding_service=embedding_service,
    )


def get_permission_service(
    db: AsyncSession = Depends(get_async_session),
) -> PermissionService:
    return PermissionService(db)


def get_bm25_index(
    kb_id: str,
    container: ServiceContainer = Depends(get_service_container),
) -> BM25Index:
    return container.get_bm25_index(kb_id)

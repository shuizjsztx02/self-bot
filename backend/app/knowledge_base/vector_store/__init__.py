import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class VectorStoreBackend(ABC):
    
    @abstractmethod
    async def create_collection(
        self,
        collection_name: str,
        embedding_dim: int = 768,
        metadata_schema: Optional[Dict] = None,
    ) -> bool:
        pass
    
    @abstractmethod
    async def delete_collection(self, collection_name: str) -> bool:
        pass
    
    @abstractmethod
    async def collection_exists(self, collection_name: str) -> bool:
        pass
    
    @abstractmethod
    async def insert(
        self,
        collection_name: str,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        documents: List[str],
    ) -> List[str]:
        pass
    
    @abstractmethod
    async def search(
        self,
        collection_name: str,
        query_embedding: List[float],
        top_k: int = 10,
        filter_dict: Optional[Dict] = None,
    ) -> List[Dict]:
        pass
    
    @abstractmethod
    async def delete(
        self,
        collection_name: str,
        ids: List[str],
    ) -> bool:
        pass
    
    @abstractmethod
    async def delete_by_metadata(
        self,
        collection_name: str,
        filter_dict: Dict,
    ) -> int:
        pass
    
    @abstractmethod
    async def count(self, collection_name: str) -> int:
        pass
    
    @abstractmethod
    async def get_by_ids(
        self,
        collection_name: str,
        ids: List[str],
    ) -> List[Dict]:
        pass


class ChromaBackend(VectorStoreBackend):
    
    def __init__(self, persist_directory: str = "./data/chroma"):
        self.persist_directory = persist_directory
        self._client = None
        self._collections: Dict = {}
    
    async def _get_client(self):
        if self._client is None:
            import chromadb
            self._client = chromadb.PersistentClient(path=self.persist_directory)
        return self._client
    
    async def create_collection(
        self,
        collection_name: str,
        embedding_dim: int = 768,
        metadata_schema: Optional[Dict] = None,
    ) -> bool:
        client = await self._get_client()
        try:
            collection = client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine", "embedding_dim": embedding_dim},
            )
            self._collections[collection_name] = collection
            return True
        except Exception as e:
            logger.error(f"Error creating collection: {e}")
            return False
    
    async def delete_collection(self, collection_name: str) -> bool:
        client = await self._get_client()
        try:
            client.delete_collection(collection_name)
            if collection_name in self._collections:
                del self._collections[collection_name]
            return True
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")
            return False
    
    async def collection_exists(self, collection_name: str) -> bool:
        client = await self._get_client()
        try:
            client.get_collection(collection_name)
            return True
        except Exception:
            return False
    
    async def insert(
        self,
        collection_name: str,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        documents: List[str],
    ) -> List[str]:
        client = await self._get_client()
        try:
            collection = await self._get_collection(collection_name)
            if collection is None:
                collection = client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
                self._collections[collection_name] = collection
            
            collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents,
            )
            return ids
        except Exception as e:
            logger.error(f"Error inserting vectors: {e}")
            return []
    
    async def _get_collection(self, collection_name: str):
        if collection_name in self._collections:
            return self._collections[collection_name]
        
        client = await self._get_client()
        try:
            collection = client.get_collection(collection_name)
            self._collections[collection_name] = collection
            return collection
        except Exception:
            return None
    
    async def search(
        self,
        collection_name: str,
        query_embedding: List[float],
        top_k: int = 10,
        filter_dict: Optional[Dict] = None,
    ) -> List[Dict]:
        client = await self._get_client()
        try:
            collection = await self._get_collection(collection_name)
            if collection is None:
                return []
            
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=filter_dict,
            )
            
            formatted_results = []
            if results and results["ids"]:
                for i, doc_id in enumerate(results["ids"][0]):
                    formatted_results.append({
                        "id": doc_id,
                        "score": 1 - results["distances"][0][i] if results["distances"] else 0,
                        "document": results["documents"][0][i] if results["documents"] else "",
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    })
            
            return formatted_results
        except Exception as e:
            logger.error(f"Error searching vectors: {e}")
            return []
    
    async def delete(
        self,
        collection_name: str,
        ids: List[str],
    ) -> bool:
        client = await self._get_client()
        try:
            collection = await self._get_collection(collection_name)
            if collection:
                collection.delete(ids=ids)
            return True
        except Exception as e:
            logger.error(f"Error deleting vectors: {e}")
            return False
    
    async def delete_by_metadata(
        self,
        collection_name: str,
        filter_dict: Dict,
    ) -> int:
        client = await self._get_client()
        try:
            collection = await self._get_collection(collection_name)
            if collection is None:
                return 0
            
            results = collection.get(where=filter_dict)
            if results and results["ids"]:
                collection.delete(ids=results["ids"])
                return len(results["ids"])
            return 0
        except Exception as e:
            logger.error(f"Error deleting by metadata: {e}")
            return 0
    
    async def count(self, collection_name: str) -> int:
        client = await self._get_client()
        try:
            collection = await self._get_collection(collection_name)
            if collection is None:
                return 0
            return collection.count()
        except Exception as e:
            logger.error(f"Error counting vectors: {e}")
            return 0
    
    async def get_by_ids(
        self,
        collection_name: str,
        ids: List[str],
    ) -> List[Dict]:
        client = await self._get_client()
        try:
            collection = await self._get_collection(collection_name)
            if collection is None:
                return []
            
            results = collection.get(ids=ids, include=["documents", "metadatas"])
            
            formatted_results = []
            if results and results["ids"]:
                for i, doc_id in enumerate(results["ids"]):
                    formatted_results.append({
                        "id": doc_id,
                        "document": results["documents"][i] if results["documents"] else "",
                        "metadata": results["metadatas"][i] if results["metadatas"] else {},
                    })
            
            return formatted_results
        except Exception as e:
            logger.error(f"Error getting by ids: {e}")
            return []


class VectorStoreFactory:
    
    _backends = {
        "chroma": ChromaBackend,
    }
    
    @classmethod
    def create(
        cls,
        backend: str = "chroma",
        **kwargs,
    ) -> VectorStoreBackend:
        if backend not in cls._backends:
            raise ValueError(f"Unknown backend: {backend}. Available: {list(cls._backends.keys())}")
        return cls._backends[backend](**kwargs)
    
    @classmethod
    def register_backend(cls, name: str, backend_class: type):
        cls._backends[name] = backend_class

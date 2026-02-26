from typing import List, Optional
from datetime import datetime
import uuid
import asyncio

from .md_storage import MDStorage, MemoryEntry
from .vector_store import ChromaVectorStore, VectorDocument
from .rag_retriever import RAGRetriever, RAGConfig
from .summarizer import MemorySummarizer
from app.config import settings


class LongTermMemory:
    def __init__(
        self,
        storage_path: str = None,
        chroma_path: str = None,
        embedding_model: str = "BAAI/bge-base-zh-v1.5",
        reranker_model: str = "BAAI/bge-reranker-base",
    ):
        self.md_storage = MDStorage(storage_path or settings.AGENT_MEMORY_PATH)
        self.vector_store = ChromaVectorStore(
            persist_directory=chroma_path or settings.AGENT_VECTOR_PATH,
        )
        self.rag_config = RAGConfig(
            embedding_model=embedding_model,
            reranker_model=reranker_model,
        )
        self.rag_retriever = RAGRetriever(
            self.vector_store,
            self.rag_config,
        )
        self.summarizer = MemorySummarizer()
        self._initialized = False
    
    async def initialize(self) -> None:
        if self._initialized:
            return
        
        await self.vector_store.initialize()
        self._initialized = True
    
    async def store(
        self,
        content: str,
        importance: Optional[int] = None,
        category: str = "general",
        tags: Optional[List[str]] = None,
        source_conversation_id: Optional[str] = None,
    ) -> MemoryEntry:
        await self.initialize()
        
        if importance is None:
            importance = await self.summarizer.assess_importance(content)
        
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            content=content,
            importance=importance,
            category=category,
            tags=tags or [],
            source_conversation_id=source_conversation_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        await self.md_storage.save(entry)
        
        await self._index_entry(entry)
        
        return entry
    
    async def _index_entry(self, entry: MemoryEntry) -> None:
        doc = VectorDocument(
            id=entry.id,
            content=entry.content,
            metadata={
                "importance": entry.importance,
                "category": entry.category,
                "tags": entry.tags,
                "created_at": entry.created_at.isoformat(),
            },
        )
        
        embedding = await self.rag_retriever.embed_text(entry.content)
        
        await self.vector_store.insert([doc], [embedding])
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_importance: Optional[int] = None,
        use_rerank: bool = True,
    ) -> List[tuple[MemoryEntry, float]]:
        await self.initialize()
        
        results = await self.rag_retriever.retrieve(
            query=query,
            top_k=top_k,
            use_rerank=use_rerank,
        )
        
        entries = []
        for content, score, metadata in results:
            if min_importance and metadata.get("importance", 0) < min_importance:
                continue
            
            entry = MemoryEntry(
                id=metadata.get("id", str(uuid.uuid4())),
                content=content,
                importance=metadata.get("importance", 3),
                category=metadata.get("category", "general"),
                tags=metadata.get("tags", []),
                created_at=datetime.fromisoformat(metadata["created_at"]) 
                          if "created_at" in metadata else datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            entries.append((entry, score))
        
        return entries
    
    async def get_by_id(self, entry_id: str) -> Optional[MemoryEntry]:
        return await self.md_storage.load(entry_id)
    
    async def delete(self, entry_id: str) -> bool:
        deleted = await self.md_storage.delete(entry_id)
        
        if deleted:
            await self.vector_store.delete([entry_id])
        
        return deleted
    
    async def get_context_for_query(
        self,
        query: str,
        max_tokens: int = 2000,
    ) -> str:
        results = await self.retrieve(query, top_k=5)
        
        if not results:
            return ""
        
        context_parts = []
        current_tokens = 0
        
        for entry, score in results:
            estimated_tokens = len(entry.content.split()) * 1.5
            
            if current_tokens + estimated_tokens > max_tokens:
                break
            
            context_parts.append(
                f"[重要度:{entry.importance}] {entry.content}"
            )
            current_tokens += estimated_tokens
        
        return "\n\n".join(context_parts)
    
    async def list_by_importance(self, level: int) -> List[MemoryEntry]:
        return await self.md_storage.list_by_level(level)
    
    async def list_all(self) -> List[MemoryEntry]:
        return await self.md_storage.list_all()
    
    async def get_stats(self) -> dict:
        all_entries = await self.list_all()
        
        by_importance = {}
        for entry in all_entries:
            level = entry.importance
            by_importance[level] = by_importance.get(level, 0) + 1
        
        return {
            "total_memories": len(all_entries),
            "by_importance": by_importance,
            "vector_count": await self.vector_store.count(),
        }
    
    async def clear(self) -> None:
        await self.vector_store.clear()
        all_entries = await self.list_all()
        for entry in all_entries:
            await self.md_storage.delete(entry.id)

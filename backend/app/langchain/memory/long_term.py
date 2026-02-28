from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel
import uuid
import asyncio
import math
import logging

from .md_storage import MDStorage, MemoryEntry
from .vector_store import ChromaVectorStore, VectorDocument
from .rag_retriever import RAGRetriever, RAGConfig
from .summarizer import MemorySummarizer
from app.config import settings
from app.langchain.tracing.memory_trace import (
    start_memory_trace,
    end_memory_trace,
    memory_trace_step,
    get_memory_trace,
)

logger = logging.getLogger(__name__)


class TimeDecayConfig(BaseModel):
    """时间衰减配置"""
    half_life_days: float = 30.0
    min_decay: float = 0.1
    max_decay: float = 0.9
    enable_time_decay: bool = True


class LongTermMemory:
    def __init__(
        self,
        storage_path: str = None,
        chroma_path: str = None,
        embedding_model: str = "BAAI/bge-base-zh-v1.5",
        reranker_model: str = "BAAI/bge-reranker-base",
        time_decay_config: Optional[TimeDecayConfig] = None,
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
        self.time_decay_config = time_decay_config or TimeDecayConfig()
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
        content_preview = content[:100] + "..." if len(content) > 100 else content
        
        with memory_trace_step("long_term_store", "long_term", {
            "content_len": len(content),
            "content_preview": content_preview,
            "category": category,
            "importance": importance,
            "tags": tags,
            "conversation_id": source_conversation_id,
        }):
            await self.initialize()
            
            if importance is None:
                with memory_trace_step("assess_importance", "summary", {"content_len": len(content)}):
                    importance = await self.summarizer.assess_importance(content)
            
            entry = MemoryEntry(
                id=str(uuid.uuid4()),
                content=content,
                importance=importance,
                category=category,
                tags=tags or [],
                source_conversation_id=source_conversation_id,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            
            await self.md_storage.save(entry)
            
            await self._index_entry(entry)
            
            logger.info(f"[LongTermMemory] Stored: id={entry.id}, importance={importance}, category={category}")
            
            return entry
    
    async def _index_entry(self, entry: MemoryEntry) -> None:
        with memory_trace_step("vector_index", "vector", {"entry_id": entry.id, "content_len": len(entry.content)}):
            metadata = {
                "importance": entry.importance,
                "category": entry.category,
                "created_at": entry.created_at.isoformat(),
            }
            
            if entry.tags:
                metadata["tags"] = entry.tags
            
            doc = VectorDocument(
                id=entry.id,
                content=entry.content,
                metadata=metadata,
            )
            
            with memory_trace_step("embedding", "vector", {"content_len": len(entry.content)}):
                embedding = await self.rag_retriever.embed_text(entry.content)
            
            await self.vector_store.insert([doc], [embedding])
    
    def _apply_time_decay(
        self,
        results: List[tuple[MemoryEntry, float]],
    ) -> List[tuple[MemoryEntry, float]]:
        if not self.time_decay_config.enable_time_decay:
            return results
        
        now = datetime.now(timezone.utc)
        decayed_results = []
        
        for entry, score in results:
            age_days = (now - entry.created_at).days
            age_hours = (now - entry.created_at).total_seconds() / 3600
            
            half_life = self.time_decay_config.half_life_days
            decay_factor = math.exp(-age_days / half_life)
            
            decay_factor = max(
                self.time_decay_config.min_decay,
                decay_factor
            )
            decay_factor = min(
                decay_factor,
                self.time_decay_config.max_decay
            )
            
            decayed_score = score * decay_factor
            
            decayed_results.append((entry, decayed_score))
        
        decayed_results.sort(key=lambda x: x[1], reverse=True)
        
        return decayed_results
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_importance: Optional[int] = None,
        use_rerank: bool = True,
        apply_time_decay: bool = True,
    ) -> List[tuple[MemoryEntry, float]]:
        query_preview = query[:100] + "..." if len(query) > 100 else query
        
        with memory_trace_step("long_term_retrieve", "long_term", {
            "query": query_preview,
            "top_k": top_k,
            "min_importance": min_importance,
            "use_rerank": use_rerank,
            "apply_time_decay": apply_time_decay,
        }):
            await self.initialize()
            
            with memory_trace_step("vector_search", "vector", {"query": query_preview, "top_k": top_k}):
                results = await self.rag_retriever.retrieve(
                    query=query,
                    top_k=top_k,
                    use_rerank=use_rerank,
                )
            
            entries = []
            for content, score, metadata in results:
                if min_importance and metadata.get("importance", 0) < min_importance:
                    continue
                
                created_at = None
                if "created_at" in metadata:
                    try:
                        created_at = datetime.fromisoformat(metadata["created_at"])
                        if created_at.tzinfo is None:
                            created_at = created_at.replace(tzinfo=timezone.utc)
                    except:
                        created_at = datetime.now(timezone.utc)
                else:
                    created_at = datetime.now(timezone.utc)
                
                entry = MemoryEntry(
                    id=metadata.get("id", str(uuid.uuid4())),
                    content=content,
                    importance=metadata.get("importance", 3),
                    category=metadata.get("category", "general"),
                    tags=metadata.get("tags", []),
                    created_at=created_at,
                    updated_at=datetime.now(timezone.utc),
                )
                entries.append((entry, score))
            
            if apply_time_decay:
                with memory_trace_step("time_decay", "long_term", {
                    "entry_count": len(entries),
                    "half_life_days": self.time_decay_config.half_life_days,
                }):
                    entries = self._apply_time_decay(entries)
            
            result_preview = [
                {"content": e.content[:50] + "...", "score": round(s, 3)}
                for e, s in entries[:3]
            ]
            
            logger.info(f"[LongTermMemory] Retrieved: {len(entries)} entries for query")
            
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
        query_preview = query[:100] + "..." if len(query) > 100 else query
        
        with memory_trace_step("get_context_for_query", "long_term", {
            "query": query_preview,
            "max_tokens": max_tokens,
        }):
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
            
            context = "\n\n".join(context_parts)
            
            return context
    
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
            "time_decay_config": {
                "half_life_days": self.time_decay_config.half_life_days,
                "enable_time_decay": self.time_decay_config.enable_time_decay,
            },
        }
    
    async def clear(self) -> None:
        await self.vector_store.clear()
        all_entries = await self.list_all()
        for entry in all_entries:
            await self.md_storage.delete(entry.id)

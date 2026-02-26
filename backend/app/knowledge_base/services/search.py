from typing import List, Optional, Dict, Any, TYPE_CHECKING
import asyncio
import time
import logging
import os

from ..schemas import SearchResult
from ..vector_store import VectorStoreBackend
from .embedding import EmbeddingService
from .bm25 import BM25Index, BM25Document, HybridSearchResult
from .attribution import SourceAttribution, RAGResponse, SourceReference
from .compression import ContextCompressor, CompressionConfig, CompressedDocument
from ..models import KnowledgeBase, Document
from app.config import settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class SearchService:
    
    def __init__(
        self,
        vector_store: VectorStoreBackend,
        embedding_service: EmbeddingService,
        reranker_model: str = "BAAI/bge-reranker-base",
        bm25_persist_path: str = None,
        compression_config: Optional[CompressionConfig] = None,
    ):
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.reranker_model = reranker_model
        self.bm25_persist_path = bm25_persist_path or settings.KB_INDEX_PATH
        self._reranker = None
        self._bm25_indexes: Dict[str, BM25Index] = {}
        
        self._attribution = SourceAttribution(embedding_service)
        self._compressor = ContextCompressor(
            config=compression_config or CompressionConfig(),
            embedding_service=embedding_service,
        )
        
        os.makedirs(self.bm25_persist_path, exist_ok=True)
    
    @property
    def reranker(self):
        if self._reranker is None:
            try:
                from sentence_transformers import CrossEncoder
                self._reranker = CrossEncoder(
                    self.reranker_model,
                    trust_remote_code=True,
                )
            except ImportError:
                pass
        return self._reranker
    
    async def search(
        self,
        kb_id: str,
        query: str,
        top_k: int = 5,
        use_rerank: bool = True,
        filters: Optional[Dict] = None,
    ) -> List[SearchResult]:
        start_time = time.time()
        
        collection_name = f"kb_{kb_id.replace('-', '_')}"
        
        query_embedding = await self.embedding_service.embed_text(query)
        
        search_top_k = top_k * 3 if use_rerank else top_k
        
        results = await self.vector_store.search(
            collection_name=collection_name,
            query_embedding=query_embedding,
            top_k=search_top_k,
            filter_dict=filters,
        )
        
        if not results:
            return []
        
        search_results = []
        for result in results:
            score = 1 - result.get("distance", 0)
            result_metadata = result.get("metadata", {})
            
            search_results.append(SearchResult(
                chunk_id=result.get("id", ""),
                doc_id=result_metadata.get("doc_id", ""),
                doc_name="",
                kb_id=kb_id,
                kb_name="",
                content=result.get("document", ""),
                score=score,
                page_number=result_metadata.get("page_number"),
                section_title=result_metadata.get("section_title"),
                extra_data=result_metadata,
            ))
        
        if use_rerank and self.reranker and len(search_results) > top_k:
            search_results = await self._rerank(query, search_results)
        
        return search_results[:top_k]
    
    async def cross_search(
        self,
        kb_ids: List[str],
        query: str,
        top_k: int = 5,
        use_rerank: bool = True,
    ) -> List[SearchResult]:
        if not kb_ids:
            return []
        
        all_results = []
        
        tasks = [
            self.search(kb_id, query, top_k=top_k, use_rerank=False)
            for kb_id in kb_ids
        ]
        
        results_per_kb = await asyncio.gather(*tasks)
        
        for results in results_per_kb:
            all_results.extend(results)
        
        if not all_results:
            return []
        
        if use_rerank and self.reranker:
            all_results = await self._rerank(query, all_results)
        else:
            all_results.sort(key=lambda x: x.score, reverse=True)
        
        return all_results[:top_k]
    
    async def _rerank(
        self,
        query: str,
        results: List[SearchResult],
    ) -> List[SearchResult]:
        if not self.reranker or not results:
            return results
        
        pairs = [(query, r.content) for r in results]
        
        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(
            None,
            self.reranker.predict,
            pairs,
        )
        
        reranked = list(zip(results, scores))
        reranked.sort(key=lambda x: x[1], reverse=True)
        
        for result, score in reranked:
            result.score = float(score)
        
        return [r for r, _ in reranked]
    
    async def hybrid_search(
        self,
        kb_id: str,
        query: str,
        top_k: int = 5,
        alpha: float = 0.5,
        use_rerank: bool = False,
    ) -> List[SearchResult]:
        """
        混合检索：向量检索 + BM25 检索
        
        Args:
            kb_id: 知识库 ID
            query: 查询文本
            top_k: 返回结果数量
            alpha: 向量检索权重 (0-1)，1-alpha 为 BM25 权重
            use_rerank: 是否使用重排序
        
        Returns:
            混合检索结果列表
        """
        start_time = time.time()
        
        collection_name = f"kb_{kb_id.replace('-', '_')}"
        
        vector_task = self.search(
            kb_id, query, top_k=top_k * 2, use_rerank=False
        )
        
        bm25_task = self._bm25_search(kb_id, query, top_k=top_k * 2)
        
        vector_results, bm25_results = await asyncio.gather(
            vector_task, bm25_task
        )
        
        if not vector_results and not bm25_results:
            return []
        
        if not vector_results:
            return bm25_results[:top_k]
        
        if not bm25_results:
            return vector_results[:top_k]
        
        vector_tuples = [(r, r.score) for r in vector_results]
        bm25_tuples = [(BM25Document(
            id=r.chunk_id,
            content=r.content,
            metadata=r.extra_data or {},
        ), r.score) for r in bm25_results]
        
        fused_results = HybridSearchResult.reciprocal_rank_fusion(
            vector_results=vector_tuples,
            bm25_results=bm25_tuples,
            alpha=alpha,
            k=60,
        )
        
        search_results = []
        for doc, score in fused_results[:top_k]:
            if isinstance(doc, SearchResult):
                doc.score = score
                search_results.append(doc)
            else:
                search_results.append(SearchResult(
                    chunk_id=doc.id,
                    doc_id=doc.metadata.get("doc_id", ""),
                    doc_name=doc.metadata.get("doc_name", ""),
                    kb_id=kb_id,
                    kb_name="",
                    content=doc.content,
                    score=score,
                    page_number=doc.metadata.get("page_number"),
                    section_title=doc.metadata.get("section_title"),
                    extra_data=doc.metadata,
                ))
        
        if use_rerank and self.reranker and len(search_results) > top_k:
            search_results = await self._rerank(query, search_results)
        
        elapsed = time.time() - start_time
        logger.debug(
            f"Hybrid search completed in {elapsed:.3f}s, "
            f"vector={len(vector_results)}, bm25={len(bm25_results)}, "
            f"fused={len(search_results)}"
        )
        
        return search_results[:top_k]
    
    async def _bm25_search(
        self,
        kb_id: str,
        query: str,
        top_k: int = 10,
    ) -> List[SearchResult]:
        """
        BM25 关键词检索
        
        Args:
            kb_id: 知识库 ID
            query: 查询文本
            top_k: 返回结果数量
        
        Returns:
            BM25 检索结果列表
        """
        if kb_id not in self._bm25_indexes:
            logger.warning(f"BM25 index not found for kb_id: {kb_id}")
            return []
        
        bm25_index = self._bm25_indexes[kb_id]
        results = bm25_index.search(query, top_k=top_k)
        
        search_results = []
        for doc, score in results:
            search_results.append(SearchResult(
                chunk_id=doc.id,
                doc_id=doc.metadata.get("doc_id", ""),
                doc_name=doc.metadata.get("doc_name", ""),
                kb_id=kb_id,
                kb_name="",
                content=doc.content,
                score=score,
                page_number=doc.metadata.get("page_number"),
                section_title=doc.metadata.get("section_title"),
                extra_data=doc.metadata,
            ))
        
        return search_results
    
    def build_bm25_index(
        self,
        kb_id: str,
        documents: List[Dict[str, Any]],
    ) -> None:
        """
        构建 BM25 索引
        
        Args:
            kb_id: 知识库 ID
            documents: 文档列表，每个文档包含 id, content, metadata
        """
        bm25_docs = [
            BM25Document(
                id=doc["id"],
                content=doc["content"],
                metadata=doc.get("metadata", {}),
            )
            for doc in documents
        ]
        
        if kb_id not in self._bm25_indexes:
            index_path = os.path.join(self.bm25_persist_path, f"bm25_{kb_id}.json")
            self._bm25_indexes[kb_id] = BM25Index(persist_path=index_path)
        
        self._bm25_indexes[kb_id].add_documents(bm25_docs)
        logger.info(f"BM25 index built for kb_id={kb_id}, docs={len(documents)}")
    
    def update_bm25_index(
        self,
        kb_id: str,
        documents: List[Dict[str, Any]],
    ) -> None:
        """更新 BM25 索引"""
        self.build_bm25_index(kb_id, documents)
    
    def remove_from_bm25_index(
        self,
        kb_id: str,
        doc_ids: List[str],
    ) -> None:
        """从 BM25 索引中移除文档"""
        if kb_id in self._bm25_indexes:
            self._bm25_indexes[kb_id].remove_documents(doc_ids)
            logger.info(f"Removed {len(doc_ids)} docs from BM25 index for kb_id={kb_id}")
    
    def clear_bm25_index(self, kb_id: str) -> None:
        """清空 BM25 索引"""
        if kb_id in self._bm25_indexes:
            self._bm25_indexes[kb_id].clear()
            logger.info(f"Cleared BM25 index for kb_id={kb_id}")
    
    async def load_and_build_bm25_index(
        self,
        db: "AsyncSession",
        kb_id: str,
    ) -> bool:
        """
        从数据库加载文档并构建 BM25 索引
        
        Args:
            db: 数据库会话
            kb_id: 知识库 ID
            
        Returns:
            是否成功构建索引
        """
        from sqlalchemy import select
        from ..models import Document, DocumentChunk, DocumentStatus
        
        try:
            result = await db.execute(
                select(DocumentChunk)
                .join(Document, DocumentChunk.doc_id == Document.id)
                .where(Document.kb_id == kb_id)
                .where(Document.status == DocumentStatus.COMPLETED)
            )
            chunks = result.scalars().all()
            
            if not chunks:
                logger.info(f"No completed chunks found for kb_id={kb_id}")
                return False
            
            documents = [
                {
                    "id": chunk.id,
                    "content": chunk.content,
                    "metadata": {
                        "doc_id": chunk.doc_id,
                        "doc_name": "",
                        "page_number": chunk.page_number,
                        "section_title": chunk.section_title,
                    },
                }
                for chunk in chunks
            ]
            
            self.build_bm25_index(kb_id, documents)
            logger.info(f"BM25 index built for kb_id={kb_id}, chunks={len(chunks)}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to build BM25 index: {e}")
            return False
    
    async def search_by_doc_ids(
        self,
        kb_id: str,
        doc_ids: List[str],
        query: str,
        top_k: int = 5,
    ) -> List[SearchResult]:
        filters = {"doc_id": {"$in": doc_ids}}
        return await self.search(kb_id, query, top_k=top_k, filters=filters)
    
    async def search_with_attribution(
        self,
        kb_id: str,
        query: str,
        answer: str,
        top_k: int = 5,
        use_rerank: bool = True,
        rewritten_query: Optional[str] = None,
    ) -> RAGResponse:
        """
        带来源溯源的搜索
        
        Args:
            kb_id: 知识库 ID
            query: 原始查询
            answer: LLM 生成的回答
            top_k: 返回结果数量
            use_rerank: 是否使用重排序
            rewritten_query: 重写后的查询
        
        Returns:
            RAGResponse 包含回答和来源引用
        """
        results = await self.search(
            kb_id=kb_id,
            query=query,
            top_k=top_k,
            use_rerank=use_rerank,
        )
        
        return self._attribution.create_response(
            answer=answer,
            source_documents=results,
            query=query,
            rewritten_query=rewritten_query,
        )
    
    async def search_with_compression(
        self,
        kb_id: str,
        query: str,
        top_k: int = 10,
        max_tokens: int = 4000,
        use_hybrid: bool = False,
    ) -> List[CompressedDocument]:
        """
        带上下文压缩的搜索
        
        Args:
            kb_id: 知识库 ID
            query: 查询文本
            top_k: 初始检索数量
            max_tokens: 最大 Token 数
            use_hybrid: 是否使用混合检索
        
        Returns:
            压缩后的文档列表
        """
        if use_hybrid:
            results = await self.hybrid_search(
                kb_id=kb_id,
                query=query,
                top_k=top_k,
            )
        else:
            results = await self.search(
                kb_id=kb_id,
                query=query,
                top_k=top_k,
                use_rerank=True,
            )
        
        return await self._compressor.compress(
            query=query,
            documents=results,
            max_tokens=max_tokens,
        )
    
    async def full_rag_search(
        self,
        kb_ids: List[str],
        query: str,
        answer: Optional[str] = None,
        top_k: int = 5,
        max_context_tokens: int = 4000,
        use_hybrid: bool = True,
    ) -> Dict[str, Any]:
        """
        完整的 RAG 检索流程
        
        Args:
            kb_ids: 知识库 ID 列表
            query: 查询文本
            answer: LLM 回答（可选，用于溯源）
            top_k: 每个知识库返回结果数量
            max_context_tokens: 最大上下文 Token 数
            use_hybrid: 是否使用混合检索
        
        Returns:
            包含压缩上下文、原始结果和溯源信息的字典
        """
        all_results = []
        
        for kb_id in kb_ids:
            if use_hybrid:
                results = await self.hybrid_search(
                    kb_id=kb_id,
                    query=query,
                    top_k=top_k,
                )
            else:
                results = await self.search(
                    kb_id=kb_id,
                    query=query,
                    top_k=top_k,
                    use_rerank=True,
                )
            all_results.extend(results)
        
        all_results.sort(key=lambda x: x.score, reverse=True)
        all_results = all_results[:top_k * len(kb_ids)]
        
        compressed_docs = await self._compressor.compress(
            query=query,
            documents=all_results,
            max_tokens=max_context_tokens,
        )
        
        response = {
            "query": query,
            "compressed_context": "\n\n".join(
                f"[{doc.id}]\n{doc.compressed_content}"
                for doc in compressed_docs
            ),
            "compressed_documents": [
                {
                    "id": doc.id,
                    "content": doc.compressed_content,
                    "score": doc.relevance_score,
                }
                for doc in compressed_docs
            ],
            "raw_results": [
                {
                    "chunk_id": r.chunk_id,
                    "doc_id": r.doc_id,
                    "doc_name": r.doc_name,
                    "kb_id": r.kb_id,
                    "kb_name": r.kb_name,
                    "content": r.content,
                    "score": r.score,
                }
                for r in all_results
            ],
            "total_chunks": len(all_results),
            "compressed_chunks": len(compressed_docs),
        }
        
        if answer:
            rag_response = self._attribution.create_response(
                answer=answer,
                source_documents=all_results,
                query=query,
            )
            response["attribution"] = rag_response.to_dict()
            response["confidence"] = rag_response.overall_confidence
        
        return response

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
import time

from app.db.session import get_async_session
from app.auth.dependencies import get_current_active_user, get_optional_user
from app.knowledge_base.models import User, KnowledgeBase, Document
from app.knowledge_base.schemas import (
    SearchRequest,
    SearchResponse,
    SearchResult,
    HybridSearchRequest,
    CrossHybridSearchRequest,
    AttributionSearchRequest,
    RAGResponse,
    SourceReference,
    CompressionSearchRequest,
    CompressionSearchResponse,
    CompressedDocumentResponse,
)
from app.knowledge_base.services import (
    SearchService,
    PermissionService,
    KnowledgeBaseService,
    EmbeddingService,
)
from app.knowledge_base.vector_store import VectorStoreFactory
from app.knowledge_base.dependencies import (
    get_search_service,
    get_permission_service,
    get_vector_store,
)

router = APIRouter(prefix="/search", tags=["检索"])


@router.post("", response_model=SearchResponse)
async def search_knowledge_bases(
    request: SearchRequest,
    current_user: User = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_session),
    search_service: SearchService = Depends(get_search_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    start_time = time.time()
    
    if request.kb_ids:
        accessible_kbs = await permission_service.get_accessible_kbs(
            current_user.id if current_user else None
        )
        
        kb_ids = [kb for kb in request.kb_ids if kb in accessible_kbs]
        
        if not kb_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No accessible knowledge bases",
            )
    else:
        kb_ids = await permission_service.get_accessible_kbs(
            current_user.id if current_user else None
        )
        
        if not kb_ids:
            return SearchResponse(
                query=request.query,
                results=[],
                total=0,
                kb_searched=[],
                search_time_ms=0,
            )
    
    results = await search_service.cross_search(
        kb_ids=kb_ids,
        query=request.query,
        top_k=request.top_k,
        use_rerank=request.use_rerank,
    )
    
    if results:
        unique_kb_ids = list(set(r.kb_id for r in results))
        unique_doc_ids = list(set(r.doc_id for r in results))
        
        kb_result = await db.execute(
            select(KnowledgeBase).where(KnowledgeBase.id.in_(unique_kb_ids))
        )
        kbs = {kb.id: kb for kb in kb_result.scalars().all()}
        
        doc_result = await db.execute(
            select(Document).where(Document.id.in_(unique_doc_ids))
        )
        docs = {doc.id: doc for doc in doc_result.scalars().all()}
        
        for result in results:
            if result.kb_id in kbs:
                result.kb_name = kbs[result.kb_id].name
            if result.doc_id in docs:
                result.doc_name = docs[result.doc_id].filename
    
    search_time = (time.time() - start_time) * 1000
    
    return SearchResponse(
        query=request.query,
        results=results,
        total=len(results),
        kb_searched=kb_ids,
        search_time_ms=search_time,
    )


@router.post("/cross-hybrid", response_model=SearchResponse)
async def cross_hybrid_search(
    request: CrossHybridSearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
    search_service: SearchService = Depends(get_search_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    跨库混合检索：向量检索 + BM25 检索
    
    在多个知识库中进行混合搜索，使用RRF算法融合向量检索和BM25检索结果。
    
    Args:
        request: CrossHybridSearchRequest
            - query: 搜索查询
            - kb_ids: 知识库ID列表（如果为空则搜索所有有权限的知识库）
            - top_k: 返回结果数量
            - alpha: 向量检索权重(0-1)，1-alpha为BM25权重
            - use_rerank: 是否使用重排序
    
    Returns:
        SearchResponse: 搜索结果
    """
    start_time = time.time()
    
    kb_ids = request.kb_ids if request.kb_ids else []
    
    if not kb_ids:
        result = await db.execute(
            select(KnowledgeBase.id)
        )
        kb_ids = [row[0] for row in result.all()]
    
    accessible_kb_ids = []
    for kb_id in kb_ids:
        has_permission = await permission_service.has_permission(
            current_user.id, kb_id, "viewer"
        )
        if has_permission:
            accessible_kb_ids.append(kb_id)
    
    if not accessible_kb_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No accessible knowledge bases",
        )
    
    results = await search_service.cross_hybrid_search(
        kb_ids=accessible_kb_ids,
        query=request.query,
        top_k=request.top_k,
        alpha=request.alpha,
        use_rerank=request.use_rerank,
    )
    
    kb_service = KnowledgeBaseService(db, search_service.vector_store)
    
    for result in results:
        kb = await kb_service.get_by_id(result.kb_id)
        if kb:
            result.kb_name = kb.name
        
        doc_result = await db.execute(
            select(Document).where(Document.id == result.doc_id)
        )
        doc = doc_result.scalar_one_or_none()
        if doc:
            result.doc_name = doc.filename
    
    search_time = (time.time() - start_time) * 1000
    
    return SearchResponse(
        query=request.query,
        results=results,
        total=len(results),
        kb_searched=accessible_kb_ids,
        search_time_ms=search_time,
    )


@router.post("/kb/{kb_id}", response_model=SearchResponse)
async def search_single_knowledge_base(
    kb_id: str,
    request: SearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    start_time = time.time()
    
    permission_service = PermissionService(db)
    
    has_permission = await permission_service.has_permission(
        current_user.id, kb_id, "viewer"
    )
    
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    vector_store = VectorStoreFactory.create("chroma")
    embedding_service = EmbeddingService()
    search_service = SearchService(
        vector_store=vector_store,
        embedding_service=embedding_service,
    )
    
    results = await search_service.search(
        kb_id=kb_id,
        query=request.query,
        top_k=request.top_k,
        use_rerank=request.use_rerank,
        filters=request.filters,
    )
    
    kb_service = KnowledgeBaseService(db, vector_store)
    kb = await kb_service.get_by_id(kb_id)
    
    for result in results:
        if kb:
            result.kb_name = kb.name
        
        from app.knowledge_base.models import Document
        from sqlalchemy import select
        doc_result = await db.execute(
            select(Document).where(Document.id == result.doc_id)
        )
        doc = doc_result.scalar_one_or_none()
        if doc:
            result.doc_name = doc.filename
    
    search_time = (time.time() - start_time) * 1000
    
    return SearchResponse(
        query=request.query,
        results=results,
        total=len(results),
        kb_searched=[kb_id],
        search_time_ms=search_time,
    )


@router.post("/hybrid", response_model=SearchResponse)
async def hybrid_search(
    request: HybridSearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
    search_service: SearchService = Depends(get_search_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    """
    混合检索：向量检索 + BM25 检索
    
    使用RRF(Reciprocal Rank Fusion)算法融合向量检索和BM25检索结果，
    提供更准确的语义匹配和关键词匹配结合的搜索结果。
    
    Args:
        request: HybridSearchRequest
            - query: 搜索查询
            - kb_id: 知识库ID
            - top_k: 返回结果数量
            - alpha: 向量检索权重(0-1)，1-alpha为BM25权重
            - use_rerank: 是否使用重排序
    
    Returns:
        SearchResponse: 搜索结果
    """
    start_time = time.time()
    
    has_permission = await permission_service.has_permission(
        current_user.id, request.kb_id, "viewer"
    )
    
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    results = await search_service.hybrid_search(
        kb_id=request.kb_id,
        query=request.query,
        top_k=request.top_k,
        alpha=request.alpha,
        use_rerank=request.use_rerank,
    )
    
    kb_service = KnowledgeBaseService(db, search_service.vector_store)
    kb = await kb_service.get_by_id(request.kb_id)
    
    for result in results:
        if kb:
            result.kb_name = kb.name
        
        doc_result = await db.execute(
            select(Document).where(Document.id == result.doc_id)
        )
        doc = doc_result.scalar_one_or_none()
        if doc:
            result.doc_name = doc.filename
    
    search_time = (time.time() - start_time) * 1000
    
    return SearchResponse(
        query=request.query,
        results=results,
        total=len(results),
        kb_searched=[request.kb_id],
        search_time_ms=search_time,
    )


@router.post("/with-attribution", response_model=RAGResponse)
async def search_with_attribution(
    request: AttributionSearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    带来源溯源的搜索
    
    在搜索结果基础上，生成带有来源引用和置信度评分的回答。
    用于RAG场景中需要追踪信息来源的应用。
    
    Args:
        request: AttributionSearchRequest
            - query: 原始查询
            - kb_id: 知识库ID
            - answer: LLM生成的回答
            - top_k: 返回结果数量
            - use_rerank: 是否使用重排序
            - rewritten_query: 重写后的查询(可选)
    
    Returns:
        RAGResponse: 包含回答、来源引用和置信度的响应
    """
    start_time = time.time()
    
    permission_service = PermissionService(db)
    
    has_permission = await permission_service.has_permission(
        current_user.id, request.kb_id, "viewer"
    )
    
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    vector_store = VectorStoreFactory.create("chroma")
    embedding_service = EmbeddingService()
    search_service = SearchService(
        vector_store=vector_store,
        embedding_service=embedding_service,
    )
    
    rag_response = await search_service.search_with_attribution(
        kb_id=request.kb_id,
        query=request.query,
        answer=request.answer,
        top_k=request.top_k,
        use_rerank=request.use_rerank,
        rewritten_query=request.rewritten_query,
    )
    
    sources = []
    for source in rag_response.sources:
        doc_result = await db.execute(
            select(Document).where(Document.id == source.doc_id)
        )
        doc = doc_result.scalar_one_or_none()
        
        sources.append(SourceReference(
            chunk_id=source.chunk_id,
            doc_id=source.doc_id,
            doc_name=doc.filename if doc else source.doc_name,
            content=source.content,
            score=source.score,
            relevance=source.relevance,
            citation=source.citation,
        ))
    
    search_time = (time.time() - start_time) * 1000
    
    return RAGResponse(
        query=rag_response.query,
        answer=rag_response.answer,
        sources=sources,
        overall_confidence=rag_response.overall_confidence,
        rewritten_query=rag_response.rewritten_query,
        search_time_ms=search_time,
    )


@router.post("/with-compression", response_model=CompressionSearchResponse)
async def search_with_compression(
    request: CompressionSearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    带上下文压缩的搜索
    
    检索文档后，对内容进行压缩处理，提取与查询最相关的片段，
    控制总Token数在指定范围内，优化LLM输入。
    
    Args:
        request: CompressionSearchRequest
            - query: 搜索查询
            - kb_id: 知识库ID
            - top_k: 初始检索数量
            - max_tokens: 最大Token数
            - use_hybrid: 是否使用混合检索
    
    Returns:
        CompressionSearchResponse: 压缩后的搜索结果
    """
    start_time = time.time()
    
    permission_service = PermissionService(db)
    
    has_permission = await permission_service.has_permission(
        current_user.id, request.kb_id, "viewer"
    )
    
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    vector_store = VectorStoreFactory.create("chroma")
    embedding_service = EmbeddingService()
    search_service = SearchService(
        vector_store=vector_store,
        embedding_service=embedding_service,
    )
    
    compressed_docs = await search_service.search_with_compression(
        kb_id=request.kb_id,
        query=request.query,
        top_k=request.top_k,
        max_tokens=request.max_tokens,
        use_hybrid=request.use_hybrid,
    )
    
    documents = []
    total_original = 0
    total_compressed = 0
    
    for doc in compressed_docs:
        doc_result = await db.execute(
            select(Document).where(Document.id == doc.id)
        )
        db_doc = doc_result.scalar_one_or_none()
        
        documents.append(CompressedDocumentResponse(
            id=doc.id,
            original_content=doc.original_content,
            compressed_content=doc.compressed_content,
            relevance_score=doc.relevance_score,
            token_count=doc.token_count,
        ))
        total_original += len(doc.original_content.split())
        total_compressed += doc.token_count
    
    compression_ratio = total_compressed / total_original if total_original > 0 else 0
    
    return CompressionSearchResponse(
        query=request.query,
        compressed_context="\n\n".join(d.compressed_content for d in documents),
        documents=documents,
        total_original_tokens=total_original,
        total_compressed_tokens=total_compressed,
        compression_ratio=compression_ratio,
    )

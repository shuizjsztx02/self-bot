from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from app.db.session import get_async_session
from app.auth.dependencies import get_current_active_user
from app.knowledge_base.models import User, Document, DocumentStatus
from app.knowledge_base.schemas import (
    DocumentResponse,
    DocumentVersionResponse,
    ChunkResponse,
)
from app.knowledge_base.services import (
    KnowledgeBaseService,
    DocumentService,
    PermissionService,
)
from app.knowledge_base.dependencies import (
    get_document_service,
    get_permission_service,
    get_knowledge_base_service,
    get_vector_store,
    get_embedding_service,
    ServiceContainer,
)
from app.knowledge_base.parsers import ParserRouter

router = APIRouter(prefix="/documents", tags=["文档"])


async def process_document(
    doc_id: str,
    kb_id: str,
    file_path: str,
):
    """
    后台任务：处理文档
    解析文档、分块、向量化并存储
    
    Args:
        doc_id: 文档ID
        kb_id: 知识库ID
        file_path: 文件路径
    """
    from app.db.session import async_session_factory
    
    container = ServiceContainer.get_instance()
    vector_store = container.vector_store
    embedding_service = container.embedding_service
    
    async with async_session_factory() as session:
        try:
            doc_service = DocumentService(
                db=session,
                vector_store=vector_store,
                embedding_service=embedding_service,
            )
            
            await doc_service.update_status(doc_id, DocumentStatus.PROCESSING)
            
            parser_router = ParserRouter()
            chunks = await parser_router.parse_and_chunk(file_path)
            
            db_chunks = await doc_service.add_chunks(doc_id, kb_id, [
                {
                    "content": c.content,
                    "token_count": c.token_count,
                    "page_number": c.page_number,
                    "section_title": c.section_title,
                    "chunk_metadata": c.chunk_metadata,
                }
                for c in chunks
            ])
            
            await doc_service.index_chunks(kb_id, db_chunks)
            
            bm25_documents = [
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
                for chunk in db_chunks
            ]
            
            from app.knowledge_base.services.search import SearchService
            search_service = SearchService(
                vector_store=vector_store,
                embedding_service=embedding_service,
            )
            search_service.build_bm25_index(kb_id, bm25_documents)
            
            kb_service = KnowledgeBaseService(session, vector_store)
            await kb_service.update_stats(kb_id)
            
            await doc_service.update_status(doc_id, DocumentStatus.COMPLETED)
            
        except Exception as e:
            async with async_session_factory() as error_session:
                error_doc_service = DocumentService(
                    db=error_session,
                    vector_store=vector_store,
                    embedding_service=embedding_service,
                )
                await error_doc_service.update_status(
                    doc_id,
                    DocumentStatus.FAILED,
                    error_message=str(e),
                )


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    folder_id: Optional[str] = None,
    title: Optional[str] = None,
    author: Optional[str] = None,
    source: Optional[str] = None,
    tags: str = "",
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
    doc_service: DocumentService = Depends(get_document_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    has_permission = await permission_service.has_permission(
        current_user.id, kb_id, "editor"
    )
    
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    file_ext = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
    
    parser_router = ParserRouter()
    if not parser_router.is_supported(f".{file_ext}"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file_ext}",
        )
    
    file_content = await file.read()
    
    doc = await doc_service.upload_document(
        kb_id=kb_id,
        file_content=file_content,
        filename=file.filename,
        file_type=file_ext,
        user_id=current_user.id,
        folder_id=folder_id,
        metadata={
            "title": title,
            "author": author,
            "source": source,
            "tags": tags.split(",") if tags else [],
        },
    )
    
    background_tasks.add_task(
        process_document,
        doc.id,
        kb_id,
        doc.file_path,
    )
    
    return doc


@router.get("", response_model=List[DocumentResponse])
async def list_documents(
    kb_id: str,
    folder_id: Optional[str] = None,
    status: Optional[DocumentStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    doc_service: DocumentService = Depends(get_document_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    has_permission = await permission_service.has_permission(
        current_user.id, kb_id, "viewer"
    )
    
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    docs = await doc_service.list_documents(kb_id, folder_id, status, skip, limit)
    
    return docs


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: str,
    current_user: User = Depends(get_current_active_user),
    doc_service: DocumentService = Depends(get_document_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    doc = await doc_service.get_by_id(doc_id)
    
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    has_permission = await permission_service.has_permission(
        current_user.id, doc.kb_id, "viewer"
    )
    
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    return doc


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    current_user: User = Depends(get_current_active_user),
    doc_service: DocumentService = Depends(get_document_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    doc = await doc_service.get_by_id(doc_id)
    
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    has_permission = await permission_service.has_permission(
        current_user.id, doc.kb_id, "editor"
    )
    
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    success = await doc_service.delete_document(doc_id)
    
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete document")
    
    return {"message": "Document deleted successfully"}


@router.put("/{doc_id}", response_model=DocumentResponse)
async def update_document(
    doc_id: str,
    title: Optional[str] = None,
    author: Optional[str] = None,
    source: Optional[str] = None,
    tags: Optional[str] = None,
    folder_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    doc_service: DocumentService = Depends(get_document_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    doc = await doc_service.get_by_id(doc_id)
    
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    has_permission = await permission_service.has_permission(
        current_user.id, doc.kb_id, "editor"
    )
    
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    update_data = {}
    if title is not None:
        update_data["title"] = title
    if author is not None:
        update_data["author"] = author
    if source is not None:
        update_data["source"] = source
    if tags is not None:
        update_data["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    if folder_id is not None:
        update_data["folder_id"] = folder_id
    
    if update_data:
        for key, value in update_data.items():
            setattr(doc, key, value)
        await doc_service.db.commit()
        await doc_service.db.refresh(doc)
    
    return doc


@router.post("/{doc_id}/reprocess")
async def reprocess_document(
    doc_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    doc_service: DocumentService = Depends(get_document_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    doc = await doc_service.get_by_id(doc_id)
    
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    has_permission = await permission_service.has_permission(
        current_user.id, doc.kb_id, "editor"
    )
    
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    await doc_service.update_status(doc_id, DocumentStatus.PENDING)
    
    await doc_service.clear_chunks(doc_id)
    
    background_tasks.add_task(
        process_document,
        doc_id,
        doc.kb_id,
        doc.file_path,
    )
    
    return {"message": "Document reprocessing started", "document_id": doc_id}


@router.get("/{doc_id}/chunks", response_model=List[ChunkResponse])
async def get_document_chunks(
    doc_id: str,
    current_user: User = Depends(get_current_active_user),
    doc_service: DocumentService = Depends(get_document_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    doc = await doc_service.get_by_id(doc_id)
    
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    has_permission = await permission_service.has_permission(
        current_user.id, doc.kb_id, "viewer"
    )
    
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    chunks = await doc_service.get_chunks(doc_id)
    
    return chunks


@router.get("/{doc_id}/versions", response_model=List[DocumentVersionResponse])
async def get_document_versions(
    doc_id: str,
    current_user: User = Depends(get_current_active_user),
    doc_service: DocumentService = Depends(get_document_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    doc = await doc_service.get_by_id(doc_id)
    
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    
    has_permission = await permission_service.has_permission(
        current_user.id, doc.kb_id, "viewer"
    )
    
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    versions = await doc_service.get_versions(doc_id)
    
    return versions

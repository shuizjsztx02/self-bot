from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, BackgroundTasks, Form
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
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"开始处理文档: doc_id={doc_id}, kb_id={kb_id}, file_path={file_path}")
    
    from app.db.session import AsyncSessionLocal
    
    container = ServiceContainer.get_instance()
    vector_store = container.vector_store
    embedding_service = container.embedding_service
    
    async with AsyncSessionLocal() as session:
        try:
            doc_service = DocumentService(
                db=session,
                vector_store=vector_store,
                embedding_service=embedding_service,
            )
            
            logger.info(f"更新文档状态为处理中: doc_id={doc_id}")
            await doc_service.update_status(doc_id, DocumentStatus.PROCESSING)
            
            logger.info(f"开始解析文档: {file_path}")
            parser_router = ParserRouter()
            chunks = await parser_router.parse_and_chunk(file_path)
            logger.info(f"文档解析完成，共 {len(chunks)} 个分块")
            
            logger.info(f"添加分块到数据库: doc_id={doc_id}")
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
            logger.info(f"已添加 {len(db_chunks)} 个分块到数据库")
            
            logger.info(f"开始向量化分块: kb_id={kb_id}")
            await doc_service.index_chunks(kb_id, db_chunks)
            logger.info(f"向量化完成")
            
            logger.info(f"构建 BM25 索引: kb_id={kb_id}")
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
            logger.info(f"BM25 索引构建完成")
            
            kb_service = KnowledgeBaseService(session, vector_store)
            await kb_service.update_stats(kb_id)
            logger.info(f"知识库统计更新完成")
            
            await doc_service.update_status(doc_id, DocumentStatus.COMPLETED)
            logger.info(f"文档处理完成: doc_id={doc_id}")
            
        except Exception as e:
            logger.error(f"文档处理失败: doc_id={doc_id}, error={e}", exc_info=True)
            async with AsyncSessionLocal() as error_session:
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
    background_tasks: BackgroundTasks,
    kb_id: str = Form(...),
    file: UploadFile = File(...),
    folder_id: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
    source: Optional[str] = Form(None),
    tags: str = Form(""),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
    doc_service: DocumentService = Depends(get_document_service),
    permission_service: PermissionService = Depends(get_permission_service),
):
    import logging
    logger = logging.getLogger(__name__)
    
    has_permission = await permission_service.has_permission(
        current_user.id, kb_id, "editor"
    )
    
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    file_ext = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
    logger.info(f"Uploading file: {file.filename}, extension: {file_ext}")
    
    try:
        parser_router = ParserRouter()
        supported_exts = parser_router.supported_extensions()
        logger.info(f"Supported extensions: {supported_exts}")
        
        if not parser_router.is_supported(f".{file_ext}"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: .{file_ext}. Supported types: {', '.join(supported_exts)}",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initializing parser: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Parser initialization error: {str(e)}",
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
    
    logger.info(f"文档上传成功: doc_id={doc.id}, file_path={doc.file_path}")
    logger.info(f"添加后台任务: process_document")
    
    background_tasks.add_task(
        process_document,
        doc.id,
        kb_id,
        doc.file_path,
    )
    
    logger.info(f"后台任务已添加，返回响应")
    
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

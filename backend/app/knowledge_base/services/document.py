from typing import Optional, List
from datetime import datetime
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import uuid
import hashlib
import aiofiles
import os

from ..models import Document, DocumentVersion, DocumentChunk, DocumentStatus
from ..schemas import DocumentUpload
from ..vector_store import VectorStoreBackend
from .embedding import EmbeddingService
from app.config import settings


class DocumentService:
    
    def __init__(
        self,
        db: AsyncSession,
        vector_store: VectorStoreBackend,
        embedding_service: EmbeddingService,
        storage_path: str = None,
    ):
        self.db = db
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.storage_path = storage_path or settings.KB_DOCUMENT_PATH
    
    async def upload_document(
        self,
        kb_id: str,
        file_content: bytes,
        filename: str,
        file_type: str,
        user_id: str,
        folder_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Document:
        file_hash = hashlib.sha256(file_content).hexdigest()
        
        kb_dir = Path(self.storage_path) / kb_id / "documents"
        kb_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = kb_dir / f"{uuid.uuid4().hex}_{filename}"
        
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_content)
        
        doc = Document(
            kb_id=kb_id,
            folder_id=folder_id,
            filename=filename,
            file_path=str(file_path),
            file_type=file_type,
            file_size=len(file_content),
            file_hash=file_hash,
            title=metadata.get("title") if metadata else None,
            author=metadata.get("author") if metadata else None,
            source=metadata.get("source") if metadata else None,
            tags=metadata.get("tags", []) if metadata else [],
            status=DocumentStatus.PENDING,
            created_by=user_id,
        )
        
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)
        
        version = DocumentVersion(
            doc_id=doc.id,
            version=1,
            file_path=str(file_path),
            file_hash=file_hash,
            created_by=user_id,
        )
        
        self.db.add(version)
        await self.db.commit()
        
        return doc
    
    async def get_by_id(self, doc_id: str) -> Optional[Document]:
        result = await self.db.execute(
            select(Document)
            .options(selectinload(Document.versions), selectinload(Document.chunks))
            .where(Document.id == doc_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_hash(self, kb_id: str, file_hash: str) -> Optional[Document]:
        result = await self.db.execute(
            select(Document).where(
                Document.kb_id == kb_id,
                Document.file_hash == file_hash,
            )
        )
        return result.scalar_one_or_none()
    
    async def list_documents(
        self,
        kb_id: str,
        folder_id: Optional[str] = None,
        status: Optional[DocumentStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Document]:
        query = select(Document).where(Document.kb_id == kb_id)
        
        if folder_id:
            query = query.where(Document.folder_id == folder_id)
        if status:
            query = query.where(Document.status == status)
        
        query = query.offset(skip).limit(limit).order_by(Document.created_at.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def delete_document(self, doc_id: str) -> bool:
        doc = await self.get_by_id(doc_id)
        if doc is None:
            return False
        
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)
        
        collection_name = f"kb_{doc.kb_id.replace('-', '_')}"
        chunk_ids = [chunk.vector_id for chunk in doc.chunks if chunk.vector_id]
        if chunk_ids:
            await self.vector_store.delete(collection_name, chunk_ids)
        
        for chunk in doc.chunks:
            await self.db.delete(chunk)
        
        for version in doc.versions:
            await self.db.delete(version)
        
        await self.db.delete(doc)
        await self.db.commit()
        
        return True
    
    async def update_status(
        self,
        doc_id: str,
        status: DocumentStatus,
        parser_used: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[Document]:
        doc = await self.get_by_id(doc_id)
        if doc is None:
            return None
        
        doc.status = status
        doc.parser_used = parser_used
        doc.error_message = error_message
        doc.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(doc)
        
        return doc
    
    async def add_chunks(
        self,
        doc_id: str,
        kb_id: str,
        chunks: List[dict],
    ) -> List[DocumentChunk]:
        doc = await self.get_by_id(doc_id)
        if doc is None:
            return []
        
        db_chunks = []
        for i, chunk_data in enumerate(chunks):
            chunk = DocumentChunk(
                doc_id=doc_id,
                kb_id=kb_id,
                version=doc.current_version,
                chunk_index=i,
                content=chunk_data["content"],
                token_count=chunk_data.get("token_count", 0),
                page_number=chunk_data.get("page_number"),
                section_title=chunk_data.get("section_title"),
                chunk_metadata=chunk_data.get("chunk_metadata", {}),
            )
            db_chunks.append(chunk)
            self.db.add(chunk)
        
        await self.db.commit()
        
        for chunk in db_chunks:
            await self.db.refresh(chunk)
        
        doc.chunk_count = len(db_chunks)
        doc.token_count = sum(c.token_count for c in db_chunks)
        await self.db.commit()
        
        return db_chunks
    
    async def index_chunks(
        self,
        kb_id: str,
        chunks: List[DocumentChunk],
    ) -> int:
        if not chunks:
            return 0
        
        collection_name = f"kb_{kb_id.replace('-', '_')}"
        
        contents = [chunk.content for chunk in chunks]
        embeddings = await self.embedding_service.embed_texts(contents)
        
        ids = []
        metadatas = []
        documents = []
        
        for chunk, embedding in zip(chunks, embeddings):
            vector_id = str(uuid.uuid4())
            chunk.vector_id = vector_id
            ids.append(vector_id)
            metadatas.append({
                "doc_id": chunk.doc_id or "",
                "chunk_id": chunk.id or "",
                "chunk_index": chunk.chunk_index or 0,
                "page_number": chunk.page_number or 0,
                "section_title": chunk.section_title or "",
            })
            documents.append(chunk.content)
        
        await self.vector_store.insert(
            collection_name=collection_name,
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )
        
        await self.db.commit()
        
        return len(ids)
    
    async def create_version(
        self,
        doc_id: str,
        file_content: bytes,
        user_id: str,
        change_summary: Optional[str] = None,
    ) -> Optional[DocumentVersion]:
        doc = await self.get_by_id(doc_id)
        if doc is None:
            return None
        
        file_hash = hashlib.sha256(file_content).hexdigest()
        
        kb_dir = Path(self.storage_path) / doc.kb_id / "versions"
        kb_dir.mkdir(parents=True, exist_ok=True)
        
        version_path = kb_dir / f"v{doc.current_version + 1}_{doc.filename}"
        
        async with aiofiles.open(version_path, "wb") as f:
            await f.write(file_content)
        
        version = DocumentVersion(
            doc_id=doc_id,
            version=doc.current_version + 1,
            file_path=str(version_path),
            file_hash=file_hash,
            change_summary=change_summary,
            created_by=user_id,
        )
        
        self.db.add(version)
        
        doc.current_version += 1
        doc.file_hash = file_hash
        doc.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(version)
        
        return version
    
    async def get_versions(self, doc_id: str) -> List[DocumentVersion]:
        result = await self.db.execute(
            select(DocumentVersion)
            .where(DocumentVersion.doc_id == doc_id)
            .order_by(DocumentVersion.version.desc())
        )
        return list(result.scalars().all())
    
    async def get_chunks(self, doc_id: str) -> List[DocumentChunk]:
        result = await self.db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.doc_id == doc_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return list(result.scalars().all())
    
    async def clear_chunks(self, doc_id: str) -> int:
        """
        清除文档的所有分块
        删除数据库中的分块记录和向量存储中的向量
        
        Args:
            doc_id: 文档ID
            
        Returns:
            删除的分块数量
        """
        doc = await self.get_by_id(doc_id)
        if not doc:
            return 0
        
        result = await self.db.execute(
            select(DocumentChunk).where(DocumentChunk.doc_id == doc_id)
        )
        chunks = result.scalars().all()
        chunk_ids = [chunk.id for chunk in chunks]
        
        if chunk_ids:
            collection_name = f"kb_{doc.kb_id.replace('-', '_')}"
            try:
                await self.vector_store.delete_by_ids(collection_name, chunk_ids)
            except Exception:
                pass
        
        for chunk in chunks:
            await self.db.delete(chunk)
        
        await self.db.commit()
        
        return len(chunks)

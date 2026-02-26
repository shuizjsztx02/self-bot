from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from ..models import KnowledgeBase, Document, DocumentChunk, KBFolder
from ..schemas import KnowledgeBaseCreate, KnowledgeBaseUpdate
from ..vector_store import VectorStoreFactory, VectorStoreBackend
from .permission import PermissionService


class KnowledgeBaseService:
    
    def __init__(self, db: AsyncSession, vector_store: VectorStoreBackend = None):
        self.db = db
        self.vector_store = vector_store or VectorStoreFactory.create("chroma")
    
    async def create(
        self,
        data: KnowledgeBaseCreate,
        owner_id: str,
    ) -> KnowledgeBase:
        kb = KnowledgeBase(
            name=data.name,
            description=data.description,
            owner_id=owner_id,
            embedding_model=data.embedding_model,
            chunk_size=data.chunk_size,
            chunk_overlap=data.chunk_overlap,
            department=data.department,
            security_level=data.security_level,
        )
        
        self.db.add(kb)
        await self.db.commit()
        await self.db.refresh(kb)
        
        collection_name = f"kb_{kb.id.replace('-', '_')}"
        await self.vector_store.create_collection(collection_name)
        
        return kb
    
    async def get_by_id(self, kb_id: str) -> Optional[KnowledgeBase]:
        result = await self.db.execute(
            select(KnowledgeBase)
            .options(selectinload(KnowledgeBase.documents))
            .where(KnowledgeBase.id == kb_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_name(self, name: str) -> Optional[KnowledgeBase]:
        result = await self.db.execute(
            select(KnowledgeBase).where(KnowledgeBase.name == name)
        )
        return result.scalar_one_or_none()
    
    async def update(
        self,
        kb_id: str,
        data: KnowledgeBaseUpdate,
    ) -> Optional[KnowledgeBase]:
        kb = await self.get_by_id(kb_id)
        if kb is None:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(kb, key, value)
        
        kb.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(kb)
        
        return kb
    
    async def delete(self, kb_id: str) -> bool:
        kb = await self.get_by_id(kb_id)
        if kb is None:
            return False
        
        collection_name = f"kb_{kb_id.replace('-', '_')}"
        await self.vector_store.delete_collection(collection_name)
        
        await self.db.delete(kb)
        await self.db.commit()
        
        return True
    
    async def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        owner_id: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[KnowledgeBase]:
        query = select(KnowledgeBase)
        
        if owner_id:
            query = query.where(KnowledgeBase.owner_id == owner_id)
        if is_active is not None:
            query = query.where(KnowledgeBase.is_active == is_active)
        
        query = query.offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def list_accessible(
        self,
        user_id: str,
        permission_service: PermissionService,
    ) -> List[KnowledgeBase]:
        kb_ids = await permission_service.get_accessible_kbs(user_id)
        
        if not kb_ids:
            return []
        
        result = await self.db.execute(
            select(KnowledgeBase).where(KnowledgeBase.id.in_(kb_ids))
        )
        return list(result.scalars().all())
    
    async def get_stats(self, kb_id: str) -> dict:
        kb = await self.get_by_id(kb_id)
        if kb is None:
            return {}
        
        doc_count_result = await self.db.execute(
            select(func.count(Document.id)).where(Document.kb_id == kb_id)
        )
        doc_count = doc_count_result.scalar() or 0
        
        chunk_count_result = await self.db.execute(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.kb_id == kb_id)
        )
        chunk_count = chunk_count_result.scalar() or 0
        
        token_count_result = await self.db.execute(
            select(func.sum(DocumentChunk.token_count)).where(DocumentChunk.kb_id == kb_id)
        )
        token_count = token_count_result.scalar() or 0
        
        file_type_result = await self.db.execute(
            select(Document.file_type, func.count(Document.id))
            .where(Document.kb_id == kb_id)
            .group_by(Document.file_type)
        )
        by_file_type = {row[0]: row[1] for row in file_type_result.all()}
        
        status_result = await self.db.execute(
            select(Document.status, func.count(Document.id))
            .where(Document.kb_id == kb_id)
            .group_by(Document.status)
        )
        by_status = {row[0]: row[1] for row in status_result.all()}
        
        return {
            "total_documents": doc_count,
            "total_chunks": chunk_count,
            "total_tokens": token_count,
            "by_file_type": by_file_type,
            "by_status": by_status,
        }
    
    async def update_stats(self, kb_id: str) -> None:
        kb = await self.get_by_id(kb_id)
        if kb is None:
            return
        
        doc_count_result = await self.db.execute(
            select(func.count(Document.id)).where(Document.kb_id == kb_id)
        )
        kb.document_count = doc_count_result.scalar() or 0
        
        chunk_count_result = await self.db.execute(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.kb_id == kb_id)
        )
        kb.chunk_count = chunk_count_result.scalar() or 0
        
        await self.db.commit()
    
    async def create_folder(
        self,
        kb_id: str,
        name: str,
        parent_id: Optional[str] = None,
        inherit_permissions: bool = True,
    ) -> KBFolder:
        parent_path = ""
        if parent_id:
            parent = await self.get_folder(parent_id)
            if parent:
                parent_path = parent.path
        
        path = f"{parent_path}/{name}" if parent_path else f"/{name}"
        
        folder = KBFolder(
            kb_id=kb_id,
            parent_id=parent_id,
            name=name,
            path=path,
            inherit_permissions=inherit_permissions,
        )
        
        self.db.add(folder)
        await self.db.commit()
        await self.db.refresh(folder)
        
        return folder
    
    async def get_folder(self, folder_id: str) -> Optional[KBFolder]:
        result = await self.db.execute(
            select(KBFolder).where(KBFolder.id == folder_id)
        )
        return result.scalar_one_or_none()
    
    async def list_folders(self, kb_id: str, parent_id: Optional[str] = None) -> List[KBFolder]:
        query = select(KBFolder).where(KBFolder.kb_id == kb_id)
        
        if parent_id:
            query = query.where(KBFolder.parent_id == parent_id)
        else:
            query = query.where(KBFolder.parent_id == None)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def delete_folder(self, folder_id: str) -> bool:
        folder = await self.get_folder(folder_id)
        if folder is None:
            return False
        
        await self.db.delete(folder)
        await self.db.commit()
        
        return True

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
import uuid

from app.db.session import get_async_session
from app.auth.dependencies import get_current_active_user
from app.knowledge_base.models import User, KnowledgeBase, KBFolder, KBPermission, KBRole
from app.knowledge_base.schemas import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseResponse,
    KnowledgeBaseStats,
    FolderCreate,
    FolderUpdate,
    FolderResponse,
    PermissionGrant,
    PermissionResponse,
)
from app.knowledge_base.services import KnowledgeBaseService, PermissionService

router = APIRouter(prefix="/knowledge-bases", tags=["知识库"])


@router.post("", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    data: KnowledgeBaseCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    kb_service = KnowledgeBaseService(db)
    
    kb = await kb_service.create(data, current_user.id)
    
    return kb


@router.get("", response_model=List[KnowledgeBaseResponse])
async def list_knowledge_bases(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    owner_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    kb_service = KnowledgeBaseService(db)
    
    if owner_id is None:
        permission_service = PermissionService(db)
        kbs = await kb_service.list_accessible(current_user.id, permission_service)
    else:
        kbs = await kb_service.list_all(skip, limit, owner_id)
    
    return kbs


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    kb_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    kb_service = KnowledgeBaseService(db)
    permission_service = PermissionService(db)
    
    kb = await kb_service.get_by_id(kb_id)
    
    if kb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
    
    has_permission = await permission_service.has_permission(
        current_user.id, kb_id, "viewer"
    )
    
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    return kb


@router.put("/{kb_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge_base(
    kb_id: str,
    data: KnowledgeBaseUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    kb_service = KnowledgeBaseService(db)
    permission_service = PermissionService(db)
    
    has_permission = await permission_service.has_permission(
        current_user.id, kb_id, "admin"
    )
    
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    kb = await kb_service.update(kb_id, data)
    
    if kb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
    
    return kb


@router.delete("/{kb_id}")
async def delete_knowledge_base(
    kb_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    kb_service = KnowledgeBaseService(db)
    permission_service = PermissionService(db)
    
    kb = await kb_service.get_by_id(kb_id)
    
    if kb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
    
    if kb.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can delete knowledge base")
    
    success = await kb_service.delete(kb_id)
    
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete knowledge base")
    
    return {"message": "Knowledge base deleted successfully"}


@router.get("/{kb_id}/stats", response_model=KnowledgeBaseStats)
async def get_knowledge_base_stats(
    kb_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    kb_service = KnowledgeBaseService(db)
    permission_service = PermissionService(db)
    
    has_permission = await permission_service.has_permission(
        current_user.id, kb_id, "viewer"
    )
    
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    stats = await kb_service.get_stats(kb_id)
    
    return stats


# ==================== 文件夹管理 ====================

@router.post("/{kb_id}/folders", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(
    kb_id: str,
    data: FolderCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    permission_service = PermissionService(db)
    
    has_permission = await permission_service.has_permission(
        current_user.id, kb_id, KBRole.EDITOR
    )
    
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Editor permission required")
    
    kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = kb_result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
    
    parent_path = ""
    if data.parent_id:
        parent_result = await db.execute(select(KBFolder).where(KBFolder.id == data.parent_id, KBFolder.kb_id == kb_id))
        parent = parent_result.scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent folder not found")
        parent_path = parent.path
    
    folder_path = f"{parent_path}/{data.name}" if parent_path else f"/{data.name}"
    
    existing = await db.execute(
        select(KBFolder).where(KBFolder.kb_id == kb_id, KBFolder.path == folder_path)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Folder with this path already exists")
    
    folder = KBFolder(
        id=str(uuid.uuid4()),
        kb_id=kb_id,
        parent_id=data.parent_id,
        name=data.name,
        path=folder_path,
        inherit_permissions=data.inherit_permissions,
    )
    
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    
    return folder


@router.get("/{kb_id}/folders", response_model=List[FolderResponse])
async def list_folders(
    kb_id: str,
    parent_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    permission_service = PermissionService(db)
    
    has_permission = await permission_service.has_permission(
        current_user.id, kb_id, KBRole.VIEWER
    )
    
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    query = select(KBFolder).where(KBFolder.kb_id == kb_id)
    
    if parent_id is not None:
        query = query.where(KBFolder.parent_id == parent_id)
    else:
        query = query.where(KBFolder.parent_id == None)
    
    result = await db.execute(query.order_by(KBFolder.name))
    folders = result.scalars().all()
    
    return folders


@router.put("/{kb_id}/folders/{folder_id}", response_model=FolderResponse)
async def update_folder(
    kb_id: str,
    folder_id: str,
    data: FolderUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    permission_service = PermissionService(db)
    
    has_permission = await permission_service.has_permission(
        current_user.id, kb_id, KBRole.EDITOR
    )
    
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Editor permission required")
    
    result = await db.execute(
        select(KBFolder).where(KBFolder.id == folder_id, KBFolder.kb_id == kb_id)
    )
    folder = result.scalar_one_or_none()
    
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    
    if data.name is not None:
        old_path = folder.path
        parent_path = ""
        if folder.parent_id:
            parent_result = await db.execute(select(KBFolder).where(KBFolder.id == folder.parent_id))
            parent = parent_result.scalar_one_or_none()
            if parent:
                parent_path = parent.path
        
        new_path = f"{parent_path}/{data.name}" if parent_path else f"/{data.name}"
        
        existing = await db.execute(
            select(KBFolder).where(
                KBFolder.kb_id == kb_id,
                KBFolder.path == new_path,
                KBFolder.id != folder_id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Folder with this name already exists")
        
        folder.name = data.name
        folder.path = new_path
        
        children_result = await db.execute(
            select(KBFolder).where(KBFolder.kb_id == kb_id, KBFolder.path.like(f"{old_path}/%"))
        )
        children = children_result.scalars().all()
        for child in children:
            child.path = child.path.replace(old_path, new_path, 1)
    
    if data.inherit_permissions is not None:
        folder.inherit_permissions = data.inherit_permissions
    
    await db.commit()
    await db.refresh(folder)
    
    return folder


@router.delete("/{kb_id}/folders/{folder_id}")
async def delete_folder(
    kb_id: str,
    folder_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    permission_service = PermissionService(db)
    
    has_permission = await permission_service.has_permission(
        current_user.id, kb_id, KBRole.EDITOR
    )
    
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Editor permission required")
    
    result = await db.execute(
        select(KBFolder).where(KBFolder.id == folder_id, KBFolder.kb_id == kb_id)
    )
    folder = result.scalar_one_or_none()
    
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    
    children_count = await db.execute(
        select(func.count()).where(KBFolder.parent_id == folder_id)
    )
    if children_count.scalar() > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete folder with subfolders")
    
    from app.knowledge_base.models import Document
    docs_count = await db.execute(
        select(func.count()).where(Document.folder_id == folder_id)
    )
    if docs_count.scalar() > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete folder with documents")
    
    await db.delete(folder)
    await db.commit()
    
    return {"message": "Folder deleted successfully"}


# ==================== 权限管理 ====================

@router.get("/{kb_id}/permissions", response_model=List[PermissionResponse])
async def list_permissions(
    kb_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    permission_service = PermissionService(db)
    
    has_permission = await permission_service.has_permission(
        current_user.id, kb_id, KBRole.ADMIN
    )
    
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin permission required")
    
    permissions = await permission_service.list_kb_permissions(kb_id)
    
    return permissions


@router.post("/{kb_id}/permissions", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
async def grant_permission(
    kb_id: str,
    data: PermissionGrant,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    permission_service = PermissionService(db)
    
    has_permission = await permission_service.has_permission(
        current_user.id, kb_id, KBRole.ADMIN
    )
    
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin permission required")
    
    kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = kb_result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
    
    if data.user_id == kb.owner_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot modify owner permissions")
    
    try:
        permission = await permission_service.grant_permission(kb_id, data, current_user.id)
        return permission
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{kb_id}/permissions/{permission_id}")
async def revoke_permission(
    kb_id: str,
    permission_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    permission_service = PermissionService(db)
    
    has_permission = await permission_service.has_permission(
        current_user.id, kb_id, KBRole.ADMIN
    )
    
    if not has_permission:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin permission required")
    
    result = await db.execute(
        select(KBPermission).where(KBPermission.id == permission_id, KBPermission.kb_id == kb_id)
    )
    permission = result.scalar_one_or_none()
    
    if not permission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")
    
    kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = kb_result.scalar_one_or_none()
    if kb and permission.user_id == kb.owner_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot revoke owner permissions")
    
    success = await permission_service.revoke_permission(permission_id)
    
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to revoke permission")
    
    return {"message": "Permission revoked successfully"}

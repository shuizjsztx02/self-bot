from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from sqlalchemy.orm import selectinload
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from enum import Enum

from app.db.session import get_async_session
from app.auth.dependencies import get_current_active_user, get_superuser
from app.auth.jwt import jwt_handler
from app.knowledge_base.models import User, KBPermission, KnowledgeBase, KBRole, UserGroup, UserGroupMember

router = APIRouter(prefix="/users", tags=["用户"])


class UserListItem(BaseModel):
    id: str
    name: str
    email: str
    department: Optional[str]
    level: int
    is_active: bool
    is_superuser: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    items: List[UserListItem]
    total: int


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    level: int = Field(default=1, ge=1, le=4)
    is_superuser: bool = False


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    level: Optional[int] = Field(None, ge=1, le=4)


class UserDetail(BaseModel):
    id: str
    name: str
    email: str
    department: Optional[str]
    level: int
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LevelUpdate(BaseModel):
    level: int = Field(..., ge=1, le=4)


class StatusUpdate(BaseModel):
    is_active: bool


class SuperuserUpdate(BaseModel):
    is_superuser: bool


@router.get("", response_model=UserListResponse)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_superuser),
    db: AsyncSession = Depends(get_async_session),
):
    query = select(User)
    
    if search:
        query = query.where(
            or_(
                User.name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.department.ilike(f"%{search}%"),
            )
        )
    
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    query = query.offset(skip).limit(limit).order_by(User.created_at.desc())
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return UserListResponse(
        items=[UserListItem.model_validate(u) for u in users],
        total=total,
    )


@router.get("/all", response_model=List[UserListItem])
async def list_all_users(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(User)
        .where(User.is_active == True)
        .order_by(User.name)
    )
    users = result.scalars().all()
    
    return [UserListItem.model_validate(u) for u in users]


@router.post("", response_model=UserDetail, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    current_user: User = Depends(get_superuser),
    db: AsyncSession = Depends(get_async_session),
):
    existing = await db.execute(
        select(User).where(User.email == data.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    user = User(
        name=data.name,
        email=data.email,
        password_hash=jwt_handler.hash_password(data.password),
        department=data.department,
        level=data.level,
        is_superuser=data.is_superuser,
        is_active=True,
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return UserDetail.model_validate(user)


@router.get("/{user_id}", response_model=UserDetail)
async def get_user(
    user_id: str,
    current_user: User = Depends(get_superuser),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    return UserDetail.model_validate(user)


@router.put("/{user_id}", response_model=UserDetail)
async def update_user(
    user_id: str,
    data: UserUpdate,
    current_user: User = Depends(get_superuser),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    old_department = user.department
    
    if data.name is not None:
        user.name = data.name
    if data.department is not None:
        user.department = data.department
    if data.level is not None:
        user.level = data.level
    
    user.updated_at = datetime.utcnow()
    
    if data.department is not None and data.department != old_department:
        if data.department:
            group_result = await db.execute(
                select(UserGroup).where(UserGroup.name == data.department)
            )
            matching_group = group_result.scalar_one_or_none()
            
            if matching_group:
                existing_membership = await db.execute(
                    select(UserGroupMember).where(
                        UserGroupMember.group_id == matching_group.id,
                        UserGroupMember.user_id == user_id,
                    )
                )
                if not existing_membership.scalar_one_or_none():
                    new_membership = UserGroupMember(
                        group_id=matching_group.id,
                        user_id=user_id,
                        is_manager=False,
                    )
                    db.add(new_membership)
    
    await db.commit()
    await db.refresh(user)
    
    return UserDetail.model_validate(user)


@router.put("/{user_id}/level", response_model=UserDetail)
async def update_user_level(
    user_id: str,
    data: LevelUpdate,
    current_user: User = Depends(get_superuser),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    user.level = data.level
    user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(user)
    
    return UserDetail.model_validate(user)


@router.put("/{user_id}/status", response_model=UserDetail)
async def update_user_status(
    user_id: str,
    data: StatusUpdate,
    current_user: User = Depends(get_superuser),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    if user.id == current_user.id and not data.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate yourself",
        )
    
    user.is_active = data.is_active
    user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(user)
    
    return UserDetail.model_validate(user)


@router.put("/{user_id}/superuser", response_model=UserDetail)
async def update_user_superuser(
    user_id: str,
    data: SuperuserUpdate,
    current_user: User = Depends(get_superuser),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    if user.id == current_user.id and not data.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove superuser status from yourself",
        )
    
    user.is_superuser = data.is_superuser
    user.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(user)
    
    return UserDetail.model_validate(user)


class PermissionInfo(BaseModel):
    id: str
    kb_id: str
    kb_name: str
    role: str
    folder_id: Optional[str]
    granted_by: Optional[str]
    granted_at: datetime
    expires_at: Optional[datetime]
    source: str

    class Config:
        from_attributes = True


class PermissionGrant(BaseModel):
    kb_id: str
    role: str = Field(..., pattern="^(viewer|editor|admin|owner)$")
    folder_id: Optional[str] = None
    expires_at: Optional[datetime] = None


class PermissionListResponse(BaseModel):
    items: List[PermissionInfo]
    total: int


@router.get("/{user_id}/permissions", response_model=PermissionListResponse)
async def get_user_permissions(
    user_id: str,
    current_user: User = Depends(get_superuser),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    perm_result = await db.execute(
        select(KBPermission)
        .where(KBPermission.user_id == user_id)
        .options(selectinload(KBPermission.knowledge_base))
        .order_by(KBPermission.granted_at.desc())
    )
    permissions = perm_result.scalars().all()
    
    items = []
    for perm in permissions:
        items.append(PermissionInfo(
            id=perm.id,
            kb_id=perm.kb_id,
            kb_name=perm.knowledge_base.name if perm.knowledge_base else "Unknown",
            role=perm.role.value if hasattr(perm.role, 'value') else str(perm.role),
            folder_id=perm.folder_id,
            granted_by=perm.granted_by,
            granted_at=perm.granted_at,
            expires_at=perm.expires_at,
            source="direct",
        ))
    
    return PermissionListResponse(items=items, total=len(items))


@router.post("/{user_id}/permissions", response_model=PermissionInfo, status_code=status.HTTP_201_CREATED)
async def grant_user_permission(
    user_id: str,
    data: PermissionGrant,
    current_user: User = Depends(get_superuser),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    kb_result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == data.kb_id)
    )
    kb = kb_result.scalar_one_or_none()
    
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found",
        )
    
    existing = await db.execute(
        select(KBPermission).where(
            KBPermission.user_id == user_id,
            KBPermission.kb_id == data.kb_id,
            KBPermission.folder_id == data.folder_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Permission already exists for this user on this knowledge base",
        )
    
    role_map = {
        "viewer": KBRole.VIEWER,
        "editor": KBRole.EDITOR,
        "admin": KBRole.ADMIN,
        "owner": KBRole.OWNER,
    }
    
    permission = KBPermission(
        kb_id=data.kb_id,
        user_id=user_id,
        role=role_map[data.role],
        folder_id=data.folder_id,
        granted_by=current_user.id,
        expires_at=data.expires_at,
    )
    
    db.add(permission)
    await db.commit()
    await db.refresh(permission)
    
    return PermissionInfo(
        id=permission.id,
        kb_id=permission.kb_id,
        kb_name=kb.name,
        role=permission.role.value,
        folder_id=permission.folder_id,
        granted_by=permission.granted_by,
        granted_at=permission.granted_at,
        expires_at=permission.expires_at,
        source="direct",
    )


@router.delete("/{user_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_user_permission(
    user_id: str,
    permission_id: str,
    current_user: User = Depends(get_superuser),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(KBPermission).where(
            KBPermission.id == permission_id,
            KBPermission.user_id == user_id,
        )
    )
    permission = result.scalar_one_or_none()
    
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found",
        )
    
    await db.delete(permission)
    await db.commit()

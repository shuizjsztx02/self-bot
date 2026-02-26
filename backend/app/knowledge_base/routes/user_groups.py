from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_async_session
from app.auth.dependencies import get_current_active_user
from app.knowledge_base.models import User, UserGroup, UserGroupMember
from app.knowledge_base.schemas import (
    UserGroupCreate,
    UserGroupResponse,
)

router = APIRouter(prefix="/user-groups", tags=["用户组"])


class UserGroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[str] = None


class MemberAdd(BaseModel):
    user_id: str
    is_manager: bool = False


class MemberResponse(BaseModel):
    id: str
    user_id: str
    user_name: str
    user_email: str
    is_manager: bool
    joined_at: datetime

    class Config:
        from_attributes = True


class UserGroupDetailResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    parent_id: Optional[str]
    member_count: int
    members: List[MemberResponse]
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("", response_model=UserGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_user_group(
    data: UserGroupCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can create user groups",
        )
    
    result = await db.execute(
        select(UserGroup).where(UserGroup.name == data.name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Group name already exists",
        )
    
    if data.parent_id:
        parent_result = await db.execute(
            select(UserGroup).where(UserGroup.id == data.parent_id)
        )
        if not parent_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent group not found",
            )
    
    group = UserGroup(
        name=data.name,
        description=data.description,
        parent_id=data.parent_id,
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)
    
    return UserGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        parent_id=group.parent_id,
        member_count=0,
        created_at=group.created_at,
    )


@router.get("", response_model=List[UserGroupResponse])
async def list_user_groups(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    query = select(UserGroup)
    
    if search:
        query = query.where(
            or_(
                UserGroup.name.ilike(f"%{search}%"),
                UserGroup.description.ilike(f"%{search}%"),
            )
        )
    
    query = query.offset(skip).limit(limit).order_by(UserGroup.created_at.desc())
    
    result = await db.execute(query)
    groups = result.scalars().all()
    
    response = []
    for group in groups:
        member_count_result = await db.execute(
            select(func.count(UserGroupMember.id)).where(
                UserGroupMember.group_id == group.id
            )
        )
        member_count = member_count_result.scalar() or 0
        
        response.append(UserGroupResponse(
            id=group.id,
            name=group.name,
            description=group.description,
            parent_id=group.parent_id,
            member_count=member_count,
            created_at=group.created_at,
        ))
    
    return response


@router.get("/{group_id}", response_model=UserGroupDetailResponse)
async def get_user_group(
    group_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(
        select(UserGroup).where(UserGroup.id == group_id)
    )
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )
    
    members_result = await db.execute(
        select(UserGroupMember, User)
        .join(User, UserGroupMember.user_id == User.id)
        .where(UserGroupMember.group_id == group_id)
    )
    members_data = members_result.all()
    
    members = [
        MemberResponse(
            id=m.id,
            user_id=m.user_id,
            user_name=u.name,
            user_email=u.email,
            is_manager=m.is_manager,
            joined_at=m.joined_at,
        )
        for m, u in members_data
    ]
    
    return UserGroupDetailResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        parent_id=group.parent_id,
        member_count=len(members),
        members=members,
        created_at=group.created_at,
    )


@router.put("/{group_id}", response_model=UserGroupResponse)
async def update_user_group(
    group_id: str,
    data: UserGroupUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can update user groups",
        )
    
    result = await db.execute(
        select(UserGroup).where(UserGroup.id == group_id)
    )
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )
    
    if data.name and data.name != group.name:
        existing = await db.execute(
            select(UserGroup).where(UserGroup.name == data.name)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Group name already exists",
            )
        group.name = data.name
    
    if data.description is not None:
        group.description = data.description
    
    if data.parent_id is not None:
        if data.parent_id == group_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Group cannot be its own parent",
            )
        group.parent_id = data.parent_id
    
    await db.commit()
    await db.refresh(group)
    
    member_count_result = await db.execute(
        select(func.count(UserGroupMember.id)).where(
            UserGroupMember.group_id == group.id
        )
    )
    member_count = member_count_result.scalar() or 0
    
    return UserGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        parent_id=group.parent_id,
        member_count=member_count,
        created_at=group.created_at,
    )


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_group(
    group_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can delete user groups",
        )
    
    result = await db.execute(
        select(UserGroup).where(UserGroup.id == group_id)
    )
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )
    
    await db.delete(group)
    await db.commit()


@router.post("/{group_id}/members", status_code=status.HTTP_201_CREATED)
async def add_group_member(
    group_id: str,
    data: MemberAdd,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can add group members",
        )
    
    group_result = await db.execute(
        select(UserGroup).where(UserGroup.id == group_id)
    )
    if not group_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )
    
    user_result = await db.execute(
        select(User).where(User.id == data.user_id)
    )
    if not user_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    existing = await db.execute(
        select(UserGroupMember).where(
            UserGroupMember.group_id == group_id,
            UserGroupMember.user_id == data.user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this group",
        )
    
    member = UserGroupMember(
        group_id=group_id,
        user_id=data.user_id,
        is_manager=data.is_manager,
    )
    db.add(member)
    await db.commit()
    
    return {"message": "Member added successfully"}


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_group_member(
    group_id: str,
    user_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can remove group members",
        )
    
    result = await db.execute(
        select(UserGroupMember).where(
            UserGroupMember.group_id == group_id,
            UserGroupMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )
    
    await db.delete(member)
    await db.commit()

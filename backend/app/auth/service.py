from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

from app.knowledge_base.models import User, UserGroup, UserGroupMember
from app.knowledge_base.schemas import UserCreate, UserGroupCreate
from .jwt import jwt_handler


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(
        self,
        user_data: UserCreate,
        is_superuser: bool = False,
    ) -> User:
        existing = await self.get_user_by_email(user_data.email)
        if existing:
            raise ValueError(f"User with email {user_data.email} already exists")
        
        user = User(
            name=user_data.name,
            email=user_data.email,
            password_hash=jwt_handler.hash_password(user_data.password),
            department=user_data.department,
            level=user_data.level,
            is_superuser=is_superuser,
        )
        
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        
        return user

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.group_memberships))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        user = await self.get_user_by_email(email)
        
        if user is None:
            return None
        
        if not jwt_handler.verify_password(password, user.password_hash):
            return None
        
        if not user.is_active:
            return None
        
        return user

    async def update_user(
        self,
        user_id: str,
        name: Optional[str] = None,
        department: Optional[str] = None,
        level: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[User]:
        user = await self.get_user_by_id(user_id)
        if user is None:
            return None
        
        if name is not None:
            user.name = name
        if department is not None:
            user.department = department
        if level is not None:
            user.level = level
        if is_active is not None:
            user.is_active = is_active
        
        user.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(user)
        
        return user

    async def change_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str,
    ) -> bool:
        user = await self.get_user_by_id(user_id)
        if user is None:
            return False
        
        if not jwt_handler.verify_password(old_password, user.password_hash):
            return False
        
        user.password_hash = jwt_handler.hash_password(new_password)
        user.updated_at = datetime.utcnow()
        await self.db.commit()
        
        return True

    async def delete_user(self, user_id: str) -> bool:
        user = await self.get_user_by_id(user_id)
        if user is None:
            return False
        
        await self.db.delete(user)
        await self.db.commit()
        
        return True

    async def get_user_groups(self, user_id: str) -> List[UserGroup]:
        result = await self.db.execute(
            select(UserGroup)
            .join(UserGroupMember)
            .where(UserGroupMember.user_id == user_id)
        )
        return list(result.scalars().all())

    async def create_group(self, group_data: UserGroupCreate) -> UserGroup:
        existing = await self.get_group_by_name(group_data.name)
        if existing:
            raise ValueError(f"Group with name {group_data.name} already exists")
        
        group = UserGroup(
            name=group_data.name,
            description=group_data.description,
            parent_id=group_data.parent_id,
        )
        
        self.db.add(group)
        await self.db.commit()
        await self.db.refresh(group)
        
        return group

    async def get_group_by_id(self, group_id: str) -> Optional[UserGroup]:
        result = await self.db.execute(
            select(UserGroup)
            .options(selectinload(UserGroup.members))
            .where(UserGroup.id == group_id)
        )
        return result.scalar_one_or_none()

    async def get_group_by_name(self, name: str) -> Optional[UserGroup]:
        result = await self.db.execute(
            select(UserGroup).where(UserGroup.name == name)
        )
        return result.scalar_one_or_none()

    async def add_user_to_group(
        self,
        user_id: str,
        group_id: str,
        is_manager: bool = False,
    ) -> UserGroupMember:
        existing = await self.db.execute(
            select(UserGroupMember).where(
                UserGroupMember.user_id == user_id,
                UserGroupMember.group_id == group_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("User is already a member of this group")
        
        membership = UserGroupMember(
            user_id=user_id,
            group_id=group_id,
            is_manager=is_manager,
        )
        
        self.db.add(membership)
        await self.db.commit()
        await self.db.refresh(membership)
        
        return membership

    async def remove_user_from_group(self, user_id: str, group_id: str) -> bool:
        result = await self.db.execute(
            select(UserGroupMember).where(
                UserGroupMember.user_id == user_id,
                UserGroupMember.group_id == group_id,
            )
        )
        membership = result.scalar_one_or_none()
        
        if membership is None:
            return False
        
        await self.db.delete(membership)
        await self.db.commit()
        
        return True

    async def list_groups(self, skip: int = 0, limit: int = 100) -> List[UserGroup]:
        result = await self.db.execute(
            select(UserGroup)
            .options(selectinload(UserGroup.members))
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        result = await self.db.execute(
            select(User)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

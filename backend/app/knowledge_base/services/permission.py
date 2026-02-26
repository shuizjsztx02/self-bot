from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import selectinload

from ..models import (
    User,
    KnowledgeBase,
    KBFolder,
    KBPermission,
    KBGroupPermission,
    KBAttributeRule,
    KBRole,
    UserGroupMember,
)
from ..schemas import PermissionGrant, AttributeRuleCreate


ROLE_PRIORITY = {
    KBRole.OWNER: 4,
    KBRole.ADMIN: 3,
    KBRole.EDITOR: 2,
    KBRole.VIEWER: 1,
}


class PermissionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_permission(
        self,
        user_id: str,
        kb_id: str,
        folder_id: Optional[str] = None,
    ) -> Optional[KBRole]:
        result = await self.db.execute(
            select(KBPermission).where(
                KBPermission.user_id == user_id,
                KBPermission.kb_id == kb_id,
                KBPermission.folder_id == folder_id,
            )
        )
        perm = result.scalar_one_or_none()
        return perm.role if perm else None

    async def get_user_groups(self, user_id: str) -> List[str]:
        result = await self.db.execute(
            select(UserGroupMember.group_id).where(
                UserGroupMember.user_id == user_id
            )
        )
        return [row[0] for row in result.all()]

    async def get_group_permission(
        self,
        group_ids: List[str],
        kb_id: str,
        folder_id: Optional[str] = None,
    ) -> Optional[KBRole]:
        if not group_ids:
            return None
        
        result = await self.db.execute(
            select(KBGroupPermission).where(
                KBGroupPermission.group_id.in_(group_ids),
                KBGroupPermission.kb_id == kb_id,
                KBGroupPermission.folder_id == folder_id,
            )
        )
        perms = result.scalars().all()
        
        if not perms:
            return None
        
        highest_role = max(perms, key=lambda p: ROLE_PRIORITY.get(p.role, 0))
        return highest_role.role

    async def check_attribute_rules(
        self,
        user: User,
        kb: KnowledgeBase,
    ) -> Optional[KBRole]:
        result = await self.db.execute(
            select(KBAttributeRule).where(
                KBAttributeRule.kb_id == kb.id,
                KBAttributeRule.is_active == True,
            ).order_by(KBAttributeRule.priority.desc())
        )
        rules = result.scalars().all()
        
        matched_roles = []
        
        for rule in rules:
            user_value = getattr(user, rule.user_attribute, None)
            
            if rule.resource_attribute:
                resource_value = getattr(kb, rule.resource_attribute, None)
            else:
                resource_value = rule.target_value
            
            if user_value is None or resource_value is None:
                continue
            
            if rule.operator == "==":
                if user_value == resource_value:
                    matched_roles.append(rule.role)
            elif rule.operator == "!=":
                if user_value != resource_value:
                    matched_roles.append(rule.role)
            elif rule.operator == ">=":
                if user_value >= resource_value:
                    matched_roles.append(rule.role)
            elif rule.operator == "<=":
                if user_value <= resource_value:
                    matched_roles.append(rule.role)
            elif rule.operator == "in":
                if user_value in resource_value.split(","):
                    matched_roles.append(rule.role)
        
        if matched_roles:
            return max(matched_roles, key=lambda r: ROLE_PRIORITY.get(r, 0))
        
        return None

    async def get_effective_permission(
        self,
        user_id: str,
        kb_id: str,
        folder_id: Optional[str] = None,
    ) -> Optional[KBRole]:
        user = await self._get_user(user_id)
        if user is None:
            return None
        
        if user.is_superuser:
            return KBRole.OWNER
        
        kb = await self._get_kb(kb_id)
        if kb is None:
            return None
        
        if kb.owner_id == user_id:
            return KBRole.OWNER
        
        user_perm = await self.get_user_permission(user_id, kb_id, folder_id)
        if user_perm:
            return user_perm
        
        group_ids = await self.get_user_groups(user_id)
        group_perm = await self.get_group_permission(group_ids, kb_id, folder_id)
        if group_perm:
            return group_perm
        
        attr_perm = await self.check_attribute_rules(user, kb)
        if attr_perm:
            return attr_perm
        
        if folder_id:
            folder = await self._get_folder(folder_id)
            while folder and folder.inherit_permissions:
                parent_perm = await self.get_effective_permission(
                    user_id, kb_id, folder.parent_id
                )
                if parent_perm:
                    return parent_perm
                folder = await self._get_folder(folder.parent_id) if folder.parent_id else None
        
        return None

    async def has_permission(
        self,
        user_id: str,
        kb_id: str,
        required_role: KBRole,
        folder_id: Optional[str] = None,
    ) -> bool:
        effective_role = await self.get_effective_permission(user_id, kb_id, folder_id)
        
        if effective_role is None:
            return False
        
        return ROLE_PRIORITY.get(effective_role, 0) >= ROLE_PRIORITY.get(required_role, 0)

    async def grant_permission(
        self,
        kb_id: str,
        grant_data: PermissionGrant,
        granted_by: str,
    ) -> KBPermission:
        if grant_data.user_id:
            perm = KBPermission(
                kb_id=kb_id,
                user_id=grant_data.user_id,
                folder_id=grant_data.folder_id,
                role=KBRole(grant_data.role.value),
                granted_by=granted_by,
                expires_at=grant_data.expires_at,
            )
            self.db.add(perm)
            await self.db.commit()
            await self.db.refresh(perm)
            return perm
        elif grant_data.group_id:
            perm = KBGroupPermission(
                kb_id=kb_id,
                group_id=grant_data.group_id,
                folder_id=grant_data.folder_id,
                role=KBRole(grant_data.role.value),
                granted_by=granted_by,
                expires_at=grant_data.expires_at,
            )
            self.db.add(perm)
            await self.db.commit()
            await self.db.refresh(perm)
            return perm
        else:
            raise ValueError("Either user_id or group_id must be provided")

    async def revoke_permission(
        self,
        permission_id: str,
        is_group_permission: bool = False,
    ) -> bool:
        if is_group_permission:
            result = await self.db.execute(
                select(KBGroupPermission).where(KBGroupPermission.id == permission_id)
            )
            perm = result.scalar_one_or_none()
        else:
            result = await self.db.execute(
                select(KBPermission).where(KBPermission.id == permission_id)
            )
            perm = result.scalar_one_or_none()
        
        if perm is None:
            return False
        
        await self.db.delete(perm)
        await self.db.commit()
        return True

    async def create_attribute_rule(
        self,
        kb_id: str,
        rule_data: AttributeRuleCreate,
    ) -> KBAttributeRule:
        rule = KBAttributeRule(
            kb_id=kb_id,
            attribute_type=rule_data.attribute_type,
            operator=rule_data.operator,
            user_attribute=rule_data.user_attribute,
            resource_attribute=rule_data.resource_attribute,
            target_value=rule_data.target_value,
            role=KBRole(rule_data.role.value),
            priority=rule_data.priority,
        )
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def list_kb_permissions(self, kb_id: str) -> List[KBPermission]:
        result = await self.db.execute(
            select(KBPermission).where(KBPermission.kb_id == kb_id)
        )
        return list(result.scalars().all())

    async def list_kb_group_permissions(self, kb_id: str) -> List[KBGroupPermission]:
        result = await self.db.execute(
            select(KBGroupPermission).where(KBGroupPermission.kb_id == kb_id)
        )
        return list(result.scalars().all())

    async def get_accessible_kbs(self, user_id: str) -> List[str]:
        user = await self._get_user(user_id)
        if user is None:
            return []
        
        if user.is_superuser:
            result = await self.db.execute(select(KnowledgeBase.id))
            return [row[0] for row in result.all()]
        
        kb_ids = set()
        
        result = await self.db.execute(
            select(KBPermission.kb_id).where(KBPermission.user_id == user_id)
        )
        for row in result.all():
            kb_ids.add(row[0])
        
        group_ids = await self.get_user_groups(user_id)
        if group_ids:
            result = await self.db.execute(
                select(KBGroupPermission.kb_id).where(
                    KBGroupPermission.group_id.in_(group_ids)
                )
            )
            for row in result.all():
                kb_ids.add(row[0])
        
        result = await self.db.execute(
            select(KnowledgeBase.id).where(KnowledgeBase.owner_id == user_id)
        )
        for row in result.all():
            kb_ids.add(row[0])
        
        return list(kb_ids)

    async def _get_user(self, user_id: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def _get_kb(self, kb_id: str) -> Optional[KnowledgeBase]:
        result = await self.db.execute(
            select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
        )
        return result.scalar_one_or_none()

    async def _get_folder(self, folder_id: str) -> Optional[KBFolder]:
        result = await self.db.execute(
            select(KBFolder).where(KBFolder.id == folder_id)
        )
        return result.scalar_one_or_none()

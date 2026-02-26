from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from datetime import datetime

from app.db.session import get_async_session
from app.auth.dependencies import get_current_active_user
from app.knowledge_base.models import User, KnowledgeBase, KBAttributeRule
from app.knowledge_base.schemas import AttributeRuleCreate, AttributeRuleResponse
from app.knowledge_base.services import PermissionService

router = APIRouter(tags=["属性规则"])


@router.post("/{kb_id}/attribute-rules", response_model=AttributeRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_attribute_rule(
    kb_id: str,
    data: AttributeRuleCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can create attribute rules",
        )
    
    kb_result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    )
    kb = kb_result.scalar_one_or_none()
    if not kb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
    
    rule = KBAttributeRule(
        kb_id=kb.id,
        attribute_type=data.attribute_type,
        operator=data.operator,
        user_attribute=data.user_attribute,
        resource_attribute=data.resource_attribute,
        target_value=data.target_value,
        role=data.role.value,
        priority=data.priority,
        is_active=True,
    )
    
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    
    return rule


@router.get("/{kb_id}/attribute-rules", response_model=List[AttributeRuleResponse])
async def list_attribute_rules(
    kb_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can view attribute rules",
        )
    
    result = await db.execute(
        select(KBAttributeRule).where(KBAttributeRule.kb_id == kb_id).order_by(KBAttributeRule.priority)
    )
    
    return result.scalars().all()


@router.get("/{kb_id}/attribute-rules/{rule_id}", response_model=AttributeRuleResponse)
async def get_attribute_rule(
    kb_id: str,
    rule_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can view attribute rules",
        )
    
    result = await db.execute(
        select(KBAttributeRule).where(
            KBAttributeRule.id == rule_id,
            KBAttributeRule.kb_id == kb_id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attribute rule not found")
    
    return rule


@router.put("/{kb_id}/attribute-rules/{rule_id}", response_model=AttributeRuleResponse)
async def update_attribute_rule(
    kb_id: str,
    rule_id: str,
    data: AttributeRuleCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can update attribute rules",
        )
    
    result = await db.execute(
        select(KBAttributeRule).where(KBAttributeRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attribute rule not found")
    
    if data.attribute_type is not None:
        rule.attribute_type = data.attribute_type
    if data.operator is not None:
        rule.operator = data.operator
    if data.user_attribute is not None:
        rule.user_attribute = data.user_attribute
    if data.resource_attribute is not None:
        rule.resource_attribute = data.resource_attribute
    if data.target_value is not None:
        rule.target_value = data.target_value
    if data.role is not None:
        rule.role = data.role.value
    
    if data.priority is not None:
        rule.priority = data.priority
    if data.is_active is not None:
        rule.is_active = data.is_active
    
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(rule, key, value)
    
    await db.commit()
    await db.refresh(rule)
    
    return rule


@router.delete("/{kb_id}/attribute-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attribute_rule(
    kb_id: str,
    rule_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can delete attribute rules",
        )
    
    result = await db.execute(
        select(KBAttributeRule).where(
            KBAttributeRule.id == rule_id,
            KBAttributeRule.kb_id == kb_id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attribute rule not found")
    
    await db.delete(rule)
    await db.commit()
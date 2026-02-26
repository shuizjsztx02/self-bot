from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import Optional, List
from datetime import datetime

import uuid

from app.db.session import get_async_session
from app.auth.dependencies import get_current_active_user
from app.knowledge_base.models import User, OperationLog, KnowledgeBase
from app.knowledge_base.schemas import OperationLogResponse
from app.knowledge_base.dependencies import get_permission_service

router = APIRouter(prefix="/operation-logs", tags=["操作日志"])


class OperationLogService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def log_operation(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ) -> OperationLog:
        log = OperationLog(
            id=str(uuid.uuid4()),
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
        )
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return log
    
    async def get_logs(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[OperationLog]:
        query = select(OperationLog)
        
        if user_id:
            query = query.where(OperationLog.user_id == user_id)
        
        if action:
            query = query.where(OperationLog.action == action)
        
        if resource_type:
            query = query.where(OperationLog.resource_type == resource_type)
        
        if start_date:
            query = query.where(OperationLog.created_at >= start_date)
        
        if end_date:
            query = query.where(OperationLog.created_at <= end_date)
        
        query = query.order_by(OperationLog.created_at.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_log(self, log_id: str) -> Optional[OperationLog]:
        result = await self.db.execute(
            select(OperationLog).where(OperationLog.id == log_id)
        )
        return result.scalar_one_or_none()
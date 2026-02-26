from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from pathlib import Path

from app.db.session import get_async_session
from app.auth.dependencies import get_current_user, get_current_active_user
from app.auth.service import AuthService
from app.auth.jwt import jwt_handler
from app.knowledge_base.schemas import (
    UserCreate, UserResponse, UserLogin, TokenResponse, 
    PasswordChange, RefreshTokenBody
)

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_async_session),
):
    auth_service = AuthService(db)
    try:
        user = await auth_service.create_user(user_data)
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login(
    user_data: UserLogin,
    db: AsyncSession = Depends(get_async_session),
):
    auth_service = AuthService(db)
    
    user = await auth_service.authenticate_user(user_data.email, user_data.password)
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    access_token = jwt_handler.create_access_token(
        data={"sub": user.id, "email": user.email, "name": user.name}
    )
    refresh_token = jwt_handler.create_refresh_token(
        data={"sub": user.id}
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=30 * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: Optional[RefreshTokenBody] = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: AsyncSession = Depends(get_async_session),
):
    token = None
    if credentials:
        token = credentials.credentials
    elif body and body.refresh_token:
        token = body.refresh_token
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required in Authorization header or request body",
        )
    
    payload = jwt_handler.verify_token(token, "refresh")
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    
    user_id = payload.get("sub")
    auth_service = AuthService(db)
    user = await auth_service.get_user_by_id(user_id)
    
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    access_token = jwt_handler.create_access_token(
        data={"sub": user.id, "email": user.email, "name": user.name}
    )
    new_refresh_token = jwt_handler.create_refresh_token(
        data={"sub": user.id}
    )
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=30 * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user = Depends(get_current_active_user),
):
    return current_user


@router.put("/me/password")
async def change_password(
    data: PasswordChange,
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    auth_service = AuthService(db)
    
    success = await auth_service.change_password(
        current_user.id,
        data.current_password,
        data.new_password,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid current password",
        )
    
    return {"message": "Password changed successfully"}

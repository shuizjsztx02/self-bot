from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import jwt, JWTError
import bcrypt
import os

from app.config import settings


class JWTHandler:
    def __init__(
        self,
        secret_key: str = None,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 30,
        refresh_token_expire_days: int = 7,
    ):
        self.secret_key = secret_key or os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days

    def create_access_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({
            "exp": expire,
            "type": "access",
        })
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        
        to_encode.update({
            "exp": expire,
            "type": "refresh",
        })
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            if payload.get("type") != token_type:
                return None
            
            return payload
        except JWTError:
            return None

    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
        except JWTError:
            return None

    def hash_password(self, password: str) -> str:
        # Use bcrypt directly to avoid passlib compatibility issues
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        # Use bcrypt directly for verification
        password_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)


jwt_handler = JWTHandler()


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    return jwt_handler.create_access_token(data, expires_delta)


def create_refresh_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    return jwt_handler.create_refresh_token(data, expires_delta)


def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
    return jwt_handler.verify_token(token, token_type)

from sqlalchemy import Column, String, Boolean, Integer, DateTime, Text, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List
from enum import Enum
import uuid


class Base(DeclarativeBase):
    pass


class KBRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class User(Base):
    __tablename__ = "kb_users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    department = Column(String(100), nullable=True)
    level = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    group_memberships = relationship("UserGroupMember", back_populates="user")
    permissions = relationship("KBPermission", back_populates="user", foreign_keys="KBPermission.user_id")
    owned_kbs = relationship("KnowledgeBase", back_populates="owner")
    documents = relationship("Document", back_populates="creator")


class UserGroup(Base):
    __tablename__ = "kb_user_groups"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    parent_id = Column(String(36), ForeignKey("kb_user_groups.id"), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    members = relationship("UserGroupMember", back_populates="group")
    group_permissions = relationship("KBGroupPermission", back_populates="group")


class UserGroupMember(Base):
    __tablename__ = "kb_user_group_members"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id = Column(String(36), ForeignKey("kb_user_groups.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("kb_users.id"), nullable=False)
    is_manager = Column(Boolean, default=False)
    joined_at = Column(DateTime, default=func.now())

    group = relationship("UserGroup", back_populates="members")
    user = relationship("User", back_populates="group_memberships")


class KnowledgeBase(Base):
    __tablename__ = "kb_knowledge_bases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(String(36), ForeignKey("kb_users.id"), nullable=False)

    embedding_model = Column(String(200), default="BAAI/bge-base-zh-v1.5")
    chunk_size = Column(Integer, default=500)
    chunk_overlap = Column(Integer, default=50)
    parser_config = Column(JSON, default=dict)

    department = Column(String(100), nullable=True)
    security_level = Column(Integer, default=1)

    document_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    owner = relationship("User", back_populates="owned_kbs")
    folders = relationship("KBFolder", back_populates="knowledge_base")
    documents = relationship("Document", back_populates="knowledge_base")
    user_permissions = relationship("KBPermission", back_populates="knowledge_base")
    group_permissions = relationship("KBGroupPermission", back_populates="knowledge_base")
    attribute_rules = relationship("KBAttributeRule", back_populates="knowledge_base")


class KBFolder(Base):
    __tablename__ = "kb_folders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kb_id = Column(String(36), ForeignKey("kb_knowledge_bases.id"), nullable=False)
    parent_id = Column(String(36), ForeignKey("kb_folders.id"), nullable=True)
    name = Column(String(200), nullable=False)
    path = Column(String(500), nullable=False)
    inherit_permissions = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    knowledge_base = relationship("KnowledgeBase", back_populates="folders")
    children = relationship("KBFolder", backref="parent", remote_side=[id])


class KBPermission(Base):
    __tablename__ = "kb_permissions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kb_id = Column(String(36), ForeignKey("kb_knowledge_bases.id"), nullable=False)
    folder_id = Column(String(36), ForeignKey("kb_folders.id"), nullable=True)
    user_id = Column(String(36), ForeignKey("kb_users.id"), nullable=False)
    role = Column(SQLEnum(KBRole), nullable=False, default=KBRole.VIEWER)
    granted_by = Column(String(36), ForeignKey("kb_users.id"), nullable=True)
    granted_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=True)

    knowledge_base = relationship("KnowledgeBase", back_populates="user_permissions")
    user = relationship("User", back_populates="permissions", foreign_keys=[user_id])


class KBGroupPermission(Base):
    __tablename__ = "kb_group_permissions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kb_id = Column(String(36), ForeignKey("kb_knowledge_bases.id"), nullable=False)
    folder_id = Column(String(36), ForeignKey("kb_folders.id"), nullable=True)
    group_id = Column(String(36), ForeignKey("kb_user_groups.id"), nullable=False)
    role = Column(SQLEnum(KBRole), nullable=False, default=KBRole.VIEWER)
    granted_by = Column(String(36), ForeignKey("kb_users.id"), nullable=True)
    granted_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=True)

    knowledge_base = relationship("KnowledgeBase", back_populates="group_permissions")
    group = relationship("UserGroup", back_populates="group_permissions")


class KBAttributeRule(Base):
    __tablename__ = "kb_attribute_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kb_id = Column(String(36), ForeignKey("kb_knowledge_bases.id"), nullable=False)
    attribute_type = Column(String(50), nullable=False)
    operator = Column(String(20), nullable=False, default="==")
    user_attribute = Column(String(50), nullable=False)
    resource_attribute = Column(String(50), nullable=True)
    target_value = Column(String(255), nullable=True)
    role = Column(SQLEnum(KBRole), nullable=False, default=KBRole.VIEWER)
    priority = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    knowledge_base = relationship("KnowledgeBase", back_populates="attribute_rules")


class Document(Base):
    __tablename__ = "kb_documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    kb_id = Column(String(36), ForeignKey("kb_knowledge_bases.id"), nullable=False)
    folder_id = Column(String(36), ForeignKey("kb_folders.id"), nullable=True)

    filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(Integer, default=0)
    file_hash = Column(String(64), nullable=True)

    title = Column(String(500), nullable=True)
    author = Column(String(200), nullable=True)
    source = Column(String(500), nullable=True)
    tags = Column(JSON, default=list)

    status = Column(SQLEnum(DocumentStatus), default=DocumentStatus.PENDING)
    parser_used = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)

    current_version = Column(Integer, default=1)
    chunk_count = Column(Integer, default=0)
    token_count = Column(Integer, default=0)

    created_by = Column(String(36), ForeignKey("kb_users.id"), nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    creator = relationship("User", back_populates="documents")
    versions = relationship("DocumentVersion", back_populates="document")
    chunks = relationship("DocumentChunk", back_populates="document")


class DocumentVersion(Base):
    __tablename__ = "kb_document_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doc_id = Column(String(36), ForeignKey("kb_documents.id"), nullable=False)
    version = Column(Integer, nullable=False)
    file_path = Column(String(1000), nullable=False)
    file_hash = Column(String(64), nullable=True)
    change_summary = Column(Text, nullable=True)
    created_by = Column(String(36), ForeignKey("kb_users.id"), nullable=True)
    created_at = Column(DateTime, default=func.now())

    document = relationship("Document", back_populates="versions")


class DocumentChunk(Base):
    __tablename__ = "kb_document_chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doc_id = Column(String(36), ForeignKey("kb_documents.id"), nullable=False)
    kb_id = Column(String(36), ForeignKey("kb_knowledge_bases.id"), nullable=False)
    version = Column(Integer, default=1)

    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, default=0)

    page_number = Column(Integer, nullable=True)
    section_title = Column(String(500), nullable=True)
    chunk_metadata = Column(JSON, default=dict)

    vector_id = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=func.now())

    document = relationship("Document", back_populates="chunks")


class OperationLog(Base):
    __tablename__ = "kb_operation_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("kb_users.id"), nullable=False)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(36), nullable=True)
    details = Column(JSON, default=dict)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=func.now())

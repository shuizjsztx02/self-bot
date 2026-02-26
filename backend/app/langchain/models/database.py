from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship, DeclarativeBase
from datetime import datetime
from typing import Optional
import uuid


class Base(DeclarativeBase):
    pass


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=True)
    provider = Column(String(50), default="openai")
    model = Column(String(100), nullable=True)
    system_prompt = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    memories = relationship("Memory", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=True)
    tool_calls = Column(JSON, nullable=True)
    tool_call_id = Column(String(100), nullable=True)
    name = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class Memory(Base):
    __tablename__ = "memories"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=True)
    memory_type = Column(String(50), default="long_term")
    key = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=True)
    importance = Column(Integer, default=5)
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.utcnow)
    access_count = Column(Integer, default=0)

    conversation = relationship("Conversation", back_populates="memories")


class ToolExecution(Base):
    __tablename__ = "tool_executions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False)
    message_id = Column(String(36), ForeignKey("messages.id"), nullable=False)
    tool_name = Column(String(100), nullable=False)
    tool_input = Column(JSON, nullable=True)
    tool_output = Column(Text, nullable=True)
    status = Column(String(20), default="pending")
    error = Column(Text, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Skill(Base):
    __tablename__ = "skills"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    prompt_template = Column(Text, nullable=False)
    tools = Column(JSON, nullable=True)
    parameters = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

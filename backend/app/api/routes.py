from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import uuid

from app.db import get_db
from app.langchain import MainAgent
from app.langchain.agents.supervisor_agent import SupervisorAgent
from app.langchain.agents.agent_manager import agent_manager
from app.langchain.tools import get_all_tools
from app.config import settings
from app.langchain.models.database import Conversation, Message, Memory, Skill as SkillModel
from .schemas import (
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationUpdate,
    SettingsResponse,
    ProviderInfo,
    SkillExecuteRequest,
    SkillCreateRequest,
    MemoryCreateRequest,
    MemorySearchRequest,
)

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    conversation = None
    
    if request.conversation_id:
        result = await db.execute(
            select(Conversation).where(Conversation.id == request.conversation_id)
        )
        conversation = result.scalar_one_or_none()
    
    if not conversation:
        conversation = Conversation(
            id=str(uuid.uuid4()),
            title=request.message[:50] if request.message else None,
            provider=request.provider or settings.DEFAULT_LLM_PROVIDER,
            model=request.model,
            system_prompt=request.system_prompt,
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
    
    agent = await agent_manager.get_agent(
        conversation_id=conversation.id,
        db_session=db,
        provider=request.provider or conversation.provider,
        model=request.model or conversation.model,
    )
    
    try:
        result = await agent.chat(request.message, db=db)
        
        message = Message(
            conversation_id=conversation.id,
            role="user",
            content=request.message,
        )
        db.add(message)
        
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=result.get("output", ""),
            tool_calls=result.get("tool_calls"),
        )
        db.add(assistant_message)
        await db.commit()
        
        return ChatResponse(
            conversation_id=conversation.id,
            response=result.get("output", ""),
            tool_calls=result.get("tool_calls"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    from fastapi.responses import StreamingResponse
    import json
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info(f"[API] /chat/stream request: message='{request.message[:50]}...', conversation_id={request.conversation_id}")
    
    conversation = None
    
    if request.conversation_id:
        result = await db.execute(
            select(Conversation).where(Conversation.id == request.conversation_id)
        )
        conversation = result.scalar_one_or_none()
    
    if not conversation:
        conversation = Conversation(
            id=str(uuid.uuid4()),
            title=request.message[:50] if request.message else None,
            provider=request.provider or settings.DEFAULT_LLM_PROVIDER,
            model=request.model,
            system_prompt=request.system_prompt,
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        logger.info(f"[API] Created new conversation: {conversation.id}")
    
    agent = await agent_manager.get_agent(
        conversation_id=conversation.id,
        db_session=db,
        provider=request.provider or conversation.provider,
        model=request.model or conversation.model,
    )
    
    async def generate():
        try:
            yield f"data: {json.dumps({
                'type': 'conversation_id', 
                'id': conversation.id,
                'title': conversation.title,
                'provider': conversation.provider,
                'model': conversation.model,
                'created_at': conversation.created_at.isoformat() if conversation.created_at else None,
            }, ensure_ascii=False)}\n\n"
            
            async for chunk in agent.chat_stream(request.message, db=db):
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            
            logger.info(f"[API] /chat/stream completed for conversation: {conversation.id}")
        except Exception as e:
            logger.error(f"[API] /chat/stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/conversations")
async def list_conversations(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.is_active == True)
        .order_by(Conversation.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    conversations = result.scalars().all()
    return [
        {
            "id": conv.id,
            "title": conv.title,
            "provider": conv.provider,
            "model": conv.model,
            "system_prompt": conv.system_prompt,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            "messages": [],
        }
        for conv in conversations
    ]


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    messages_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = messages_result.scalars().all()
    
    conversation_dict = {
        "id": conversation.id,
        "title": conversation.title,
        "provider": conversation.provider,
        "model": conversation.model,
        "system_prompt": conversation.system_prompt,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "tool_calls": msg.tool_calls,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            }
            for msg in messages
        ],
    }
    
    return conversation_dict


@router.post("/conversations")
async def create_conversation(
    request: ConversationCreate = Body(default=None),
    db: AsyncSession = Depends(get_db),
):
    if request is None:
        request = ConversationCreate()
    
    conversation = Conversation(
        id=str(uuid.uuid4()),
        title=request.title,
        provider=request.provider or settings.DEFAULT_LLM_PROVIDER,
        model=request.model,
        system_prompt=request.system_prompt,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    
    return {
        "id": conversation.id,
        "title": conversation.title,
        "provider": conversation.provider,
        "model": conversation.model,
        "system_prompt": conversation.system_prompt,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
        "messages": [],
    }


@router.patch("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    request: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if request.title is not None:
        conversation.title = request.title
    if request.system_prompt is not None:
        conversation.system_prompt = request.system_prompt
    
    await db.commit()
    return {"status": "updated", "conversation_id": conversation_id}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    conversation.is_active = False
    await db.commit()
    return {"status": "deleted", "conversation_id": conversation_id}


@router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    providers = []
    
    if settings.OPENAI_API_KEY:
        providers.append(ProviderInfo(
            name="openai",
            model=settings.OPENAI_MODEL,
            available=True,
        ))
    
    if settings.ANTHROPIC_API_KEY:
        providers.append(ProviderInfo(
            name="anthropic",
            model=settings.CLAUDE_MODEL,
            available=True,
        ))
    
    providers.append(ProviderInfo(
        name="ollama",
        model=settings.OLLAMA_MODEL,
        available=True,
    ))
    
    if settings.DEEPSEEK_API_KEY:
        providers.append(ProviderInfo(
            name="deepseek",
            model=settings.DEEPSEEK_MODEL,
            available=True,
        ))
    
    if settings.QWEN_API_KEY:
        providers.append(ProviderInfo(
            name="qwen",
            model=settings.QWEN_MODEL,
            available=True,
        ))
    
    if settings.GLM_API_KEY:
        providers.append(ProviderInfo(
            name="glm",
            model=settings.GLM_MODEL,
            available=True,
        ))
    
    return SettingsResponse(
        default_provider=settings.DEFAULT_LLM_PROVIDER,
        providers=providers,
    )


@router.get("/tools")
async def list_tools():
    tools = get_all_tools()
    return {
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
            }
            for tool in tools
        ]
    }


@router.get("/skills")
async def list_skills(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SkillModel).where(SkillModel.is_active == True)
    )
    skills = result.scalars().all()
    return {"skills": skills}


@router.post("/skills")
async def create_skill(
    request: SkillCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(SkillModel).where(SkillModel.name == request.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Skill already exists")
    
    skill = SkillModel(
        id=str(uuid.uuid4()),
        name=request.name,
        description=request.description,
        prompt_template=request.prompt_template,
        parameters=request.parameters,
        tools=request.required_tools,
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    
    return {"status": "created", "skill_id": skill.id}


@router.post("/skills/execute")
async def execute_skill(
    request: SkillExecuteRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SkillModel).where(SkillModel.name == request.skill_name)
    )
    skill = result.scalar_one_or_none()
    
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    agent = MainAgent()
    
    message = f"Execute skill: {skill.name}\n\n{skill.prompt_template}"
    for key, value in request.parameters.items():
        message = message.replace(f"{{{key}}}", str(value))
    
    try:
        result = await agent.chat(message, db=db)
        return {"result": result.get("output", "")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/skills/{skill_name}")
async def delete_skill(
    skill_name: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SkillModel).where(SkillModel.name == skill_name)
    )
    skill = result.scalar_one_or_none()
    
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    skill.is_active = False
    await db.commit()
    return {"status": "deleted"}


@router.post("/memory")
async def create_memory(
    request: MemoryCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    memory = Memory(
        id=str(uuid.uuid4()),
        memory_type=request.memory_type,
        key=request.key,
        content=request.content,
        importance=request.importance,
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    
    return {"status": "created", "memory_id": memory.id}


@router.post("/memory/search")
async def search_memory(
    request: MemorySearchRequest,
    db: AsyncSession = Depends(get_db),
):
    query = select(Memory)
    
    if request.memory_type:
        query = query.where(Memory.memory_type == request.memory_type)
    
    query = query.order_by(Memory.importance.desc()).limit(request.limit)
    
    result = await db.execute(query)
    memories = result.scalars().all()
    
    return {"memories": memories}


@router.get("/memory/stats")
async def get_memory_stats():
    stats = agent_manager.get_stats()
    return stats

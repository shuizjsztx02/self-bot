from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db import get_db
from app.langchain.models import Conversation, Message, Memory
from app.langchain.agents import MainAgent, SupervisorAgent
from app.langchain.llm import get_llm, get_available_providers, get_provider_info
from app.langchain.tools import get_all_tools
from app.langchain.memory import LongTermMemory
from app.config import settings
from .schemas import (
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ProviderInfo,
    SettingsResponse,
    SkillExecuteRequest,
    SkillCreateRequest,
    MemoryCreateRequest,
    MemorySearchRequest,
)
from typing import Optional
import json
import uuid

router = APIRouter()

USE_SUPERVISOR = True


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    provider_infos = []
    
    for info in get_provider_info():
        provider_infos.append(ProviderInfo(
            name=info["name"],
            model=info["model"],
            available=info["available"],
        ))

    return SettingsResponse(
        default_provider=settings.DEFAULT_LLM_PROVIDER,
        providers=provider_infos,
    )


@router.post("/conversations", response_model=dict)
async def create_conversation(
    data: ConversationCreate,
    db: AsyncSession = Depends(get_db),
):
    conversation = Conversation(
        title=data.title or "新对话",
        provider=data.provider or settings.DEFAULT_LLM_PROVIDER,
        model=data.model,
        system_prompt=data.system_prompt,
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
        "created_at": conversation.created_at.isoformat(),
    }


@router.get("/conversations", response_model=list)
async def list_conversations(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.is_active == True)
        .order_by(Conversation.updated_at.desc())
    )
    conversations = result.scalars().all()
    
    return [
        {
            "id": c.id,
            "title": c.title,
            "provider": c.provider,
            "model": c.model,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
        }
        for c in conversations
    ]


@router.get("/conversations/{conversation_id}", response_model=dict)
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

    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = msg_result.scalars().all()

    return {
        "id": conversation.id,
        "title": conversation.title,
        "provider": conversation.provider,
        "model": conversation.model,
        "system_prompt": conversation.system_prompt,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "tool_calls": m.tool_calls,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }


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
    
    return {"status": "deleted"}


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    if request.conversation_id:
        result = await db.execute(
            select(Conversation).where(Conversation.id == request.conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(
            title="新对话",
            provider=request.provider or settings.DEFAULT_LLM_PROVIDER,
            model=request.model,
            system_prompt=request.system_prompt,
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

    if USE_SUPERVISOR:
        agent = SupervisorAgent(
            provider=conversation.provider,
            model=conversation.model,
            conversation_id=conversation.id,
            db_session=db,
        )
    else:
        agent = MainAgent(
            provider=conversation.provider,
            model=conversation.model,
            system_prompt=conversation.system_prompt,
            conversation_id=conversation.id,
        )

    result = await agent.chat(request.message, db=db)
    
    response_content = result.get("output", "")
    tool_calls = result.get("tool_calls")

    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
    )
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=response_content,
        tool_calls=tool_calls,
    )
    db.add(user_msg)
    db.add(assistant_msg)
    await db.commit()

    return ChatResponse(
        conversation_id=conversation.id,
        response=response_content,
        tool_calls=tool_calls,
    )


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    session_id = str(uuid.uuid4())
    
    async def generate():
        if request.conversation_id:
            result = await db.execute(
                select(Conversation).where(Conversation.id == request.conversation_id)
            )
            conversation = result.scalar_one_or_none()
            if not conversation:
                yield f"data: {json.dumps({'error': 'Conversation not found'})}\n\n"
                return
        else:
            conversation = Conversation(
                title="新对话",
                provider=request.provider or settings.DEFAULT_LLM_PROVIDER,
                model=request.model,
                system_prompt=request.system_prompt,
            )
            db.add(conversation)
            await db.commit()
            await db.refresh(conversation)

        yield f"data: {json.dumps({'type': 'conversation_id', 'id': conversation.id, 'session_id': session_id})}\n\n"

        if USE_SUPERVISOR:
            agent = SupervisorAgent(
                provider=conversation.provider,
                model=conversation.model,
                conversation_id=conversation.id,
                db_session=db,
            )
        else:
            agent = MainAgent(
                provider=conversation.provider,
                model=conversation.model,
                system_prompt=conversation.system_prompt,
                conversation_id=conversation.id,
            )

        try:
            async for event in agent.chat_stream(request.message, db=db, session_id=session_id):
                event_type = event.get("type", "")
                
                if event_type == "content":
                    yield f"data: {json.dumps({'type': 'content', 'content': event.get('content', '')}, ensure_ascii=False)}\n\n"
                elif event_type == "tool_call":
                    yield f"data: {json.dumps({'type': 'tool_call', 'name': event.get('name'), 'arguments': event.get('arguments')}, ensure_ascii=False)}\n\n"
                elif event_type == "tool_result":
                    yield f"data: {json.dumps({'type': 'tool_result', 'name': event.get('name'), 'result': event.get('result')}, ensure_ascii=False)}\n\n"
                elif event_type == "interrupted":
                    yield f"data: {json.dumps({'type': 'interrupted', 'content': event.get('content', ''), 'message': event.get('message', '')}, ensure_ascii=False)}\n\n"
                elif event_type == "done":
                    yield f"data: {json.dumps({'type': 'done', 'content': event.get('content', '')}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )


@router.post("/chat/interrupt/{session_id}")
async def interrupt_chat(session_id: str):
    from app.langchain.agents.stream_interrupt import get_stream_interrupt_manager
    
    interrupt_manager = get_stream_interrupt_manager()
    success = await interrupt_manager.interrupt(session_id)
    
    if success:
        return {"status": "interrupted", "session_id": session_id}
    else:
        raise HTTPException(
            status_code=404, 
            detail=f"Session '{session_id}' not found or already completed"
        )


@router.get("/chat/sessions")
async def list_stream_sessions():
    from app.langchain.agents.stream_interrupt import get_stream_interrupt_manager
    
    interrupt_manager = get_stream_interrupt_manager()
    sessions = interrupt_manager.get_active_sessions()
    
    return {
        "total": len(sessions),
        "sessions": sessions,
    }


@router.get("/tools")
async def list_tools():
    from app.langchain.tools import get_all_tools_with_mcp
    tools = await get_all_tools_with_mcp()
    return [
        {
            "name": t.name,
            "description": t.description,
        }
        for t in tools
    ]


@router.get("/providers")
async def list_providers():
    return get_provider_info()


@router.get("/skills")
async def list_skills():
    from app.core import get_skill_manager
    skill_manager = get_skill_manager()
    return skill_manager.get_skill_summaries()


@router.post("/skills")
async def create_skill(
    request: SkillCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    from app.core import get_skill_manager
    skill_manager = get_skill_manager()
    
    existing = await skill_manager.get_skill(request.name)
    if existing:
        raise HTTPException(status_code=400, detail=f"Skill '{request.name}' already exists")
    
    skill = await skill_manager.create_skill(
        name=request.name,
        description=request.description,
        instructions=request.prompt_template,
        tags=request.parameters or [],
        permissions={"tools": request.required_tools or []},
    )
    
    if not skill:
        raise HTTPException(status_code=500, detail="Failed to create skill")
    
    return {
        "status": "created",
        "skill": {
            "name": skill.meta.name,
            "description": skill.meta.description,
        },
    }


@router.get("/skills/{skill_name}")
async def get_skill(skill_name: str):
    from app.core import get_skill_manager
    skill_manager = get_skill_manager()
    
    skill = await skill_manager.get_skill(skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
    
    return {
        "name": skill.meta.name,
        "description": skill.meta.description,
        "instructions": skill.instructions,
    }


@router.delete("/skills/{skill_name}")
async def delete_skill(skill_name: str):
    from app.core import get_skill_manager
    skill_manager = get_skill_manager()
    
    success = await skill_manager.delete_skill(skill_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
    
    return {"status": "deleted"}


@router.post("/skills/execute")
async def execute_skill(request: SkillExecuteRequest):
    from app.core import get_skill_manager
    skill_manager = get_skill_manager()
    
    skill = await skill_manager.get_skill(request.skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{request.skill_name}' not found")
    
    prompt = skill.instructions
    for key, value in request.parameters.items():
        prompt = prompt.replace(f"{{{key}}}", str(value))
    
    return {
        "success": True,
        "output": prompt,
    }


@router.post("/memory")
async def create_memory(
    request: MemoryCreateRequest,
    conversation_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    long_term_memory = LongTermMemory(
        storage_path=settings.MEMORY_STORAGE_PATH,
        chroma_path=settings.MEMORY_CHROMA_PATH,
        embedding_model=settings.EMBEDDING_MODEL,
        reranker_model=settings.RERANKER_MODEL,
    )
    
    entry = await long_term_memory.store(
        content=request.content,
        importance=5,
        category=request.memory_type or "user_defined",
        tags=[request.key] if request.key else [],
        source_conversation_id=conversation_id,
    )
    
    memory = Memory(
        conversation_id=conversation_id,
        memory_type=request.memory_type,
        key=request.key,
        content=request.content,
        importance=5,
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    
    return {
        "id": memory.id,
        "long_term_id": entry.id,
        "content": memory.content,
        "memory_type": memory.memory_type,
        "importance": 5,
        "created_at": memory.created_at.isoformat(),
    }


@router.post("/memory/search")
async def search_memory(
    request: MemorySearchRequest,
    conversation_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Memory)
    
    if conversation_id:
        query = query.where(Memory.conversation_id == conversation_id)
    if request.memory_type:
        query = query.where(Memory.memory_type == request.memory_type)
    
    query = query.where(Memory.content.contains(request.query))
    query = query.limit(request.limit)
    
    result = await db.execute(query)
    memories = result.scalars().all()
    
    return [
        {
            "id": m.id,
            "content": m.content,
            "memory_type": m.memory_type,
            "key": m.key,
            "importance": m.importance,
            "created_at": m.created_at.isoformat(),
        }
        for m in memories
    ]


@router.get("/memory/{memory_id}")
async def get_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Memory).where(Memory.id == memory_id)
    )
    memory = result.scalar_one_or_none()
    
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    
    return {
        "id": memory.id,
        "content": memory.content,
        "memory_type": memory.memory_type,
        "key": memory.key,
        "importance": memory.importance,
        "metadata": memory.extra_data,
        "created_at": memory.created_at.isoformat(),
        "last_accessed": memory.last_accessed.isoformat(),
        "access_count": memory.access_count,
    }


@router.delete("/memory/{memory_id}")
async def delete_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Memory).where(Memory.id == memory_id)
    )
    memory = result.scalar_one_or_none()
    
    if memory:
        await db.delete(memory)
        await db.commit()
    
    return {"status": "deleted"}


# ==================== 追踪 API ====================

@router.get("/traces")
async def list_traces(limit: int = 100):
    from app.langchain.tracing import get_tracer
    tracer = get_tracer()
    return await tracer.list_traces(limit)


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str):
    from app.langchain.tracing import get_tracer
    tracer = get_tracer()
    
    trace = tracer.get_trace(trace_id)
    if not trace:
        trace = await tracer.get_trace_from_storage(trace_id)
    
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    
    return trace.model_dump()


@router.get("/traces/{trace_id}/stats")
async def get_trace_stats(trace_id: str):
    from app.langchain.tracing import get_tracer
    tracer = get_tracer()
    
    stats = tracer.get_performance_stats(trace_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Trace not found")
    
    return stats


# ==================== 状态管理 API ====================

@router.get("/sessions")
async def list_sessions():
    from app.langchain.agents import get_state_manager
    state_manager = get_state_manager()
    
    return {
        "total_sessions": state_manager.get_session_count(),
        "active_sessions": len(state_manager.get_active_sessions()),
        "sessions": [
            {
                "session_id": s.session_id,
                "conversation_id": s.conversation_id,
                "status": s.status,
                "current_agent": s.current_agent,
                "steps_count": len(s.steps),
                "created_at": s.created_at.isoformat(),
            }
            for s in state_manager.get_active_sessions()
        ],
    }


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    from app.langchain.agents import get_state_manager
    state_manager = get_state_manager()
    
    session = await state_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return session.model_dump()

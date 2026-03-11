from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
import uuid
import logging

from app.db import get_db
from app.langchain.services.agent_manager import agent_manager
from app.langchain.tools import get_all_tools
from app.config import settings
from app.langchain.models.database import Conversation, Message, Memory, Skill as SkillModel
from app.langchain.graph import get_agent
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
    SkillInstallConfirmRequest,
)

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


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
    
    logger.info(f"[API] Using LangGraph architecture with AgentManager cache")
    
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
        logger.error(f"[API] Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    from fastapi.responses import StreamingResponse
    import json
    import logging
    from datetime import datetime, timezone
    
    logger = logging.getLogger(__name__)
    logger.info(f"[API] /chat/stream request: message='{request.message[:50]}...', conversation_id={request.conversation_id}")
    
    conversation = None
    
    if request.conversation_id:
        result = await db.execute(
            select(Conversation).where(Conversation.id == request.conversation_id)
        )
        conversation = result.scalar_one_or_none()
    
    is_new_conversation = not conversation
    
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
    
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
    )
    db.add(user_message)
    await db.commit()
    logger.info(f"[API] Saved user message for conversation: {conversation.id}")
    
    logger.info(f"[API] Using LangGraph architecture with AgentManager cache for stream")
    
    agent = await agent_manager.get_agent(
        conversation_id=conversation.id,
        db_session=db,
        provider=request.provider or conversation.provider,
        model=request.model or conversation.model,
    )
    
    async def generate():
        full_response = ""
        try:
            conv_data = {
                'type': 'conversation_id', 
                'id': conversation.id,
                'title': conversation.title,
                'provider': conversation.provider,
                'model': conversation.model,
                'created_at': conversation.created_at.isoformat() if conversation.created_at else None,
                'architecture': 'langgraph',
            }
            yield f"data: {json.dumps(conv_data, ensure_ascii=False)}\n\n"
            
            async for chunk in agent.chat_stream(request.message, db=db):
                chunk_type = chunk.get("type", "")
                if chunk_type in ("content", "chunk"):
                    full_response += chunk.get("content", "")
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            
            if full_response:
                assistant_message = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=full_response,
                )
                db.add(assistant_message)
            
            conversation.updated_at = datetime.now(timezone.utc)
            if is_new_conversation and request.message:
                conversation.title = request.message[:50]
            
            await db.commit()
            
            logger.info(f"[API] /chat/stream completed for conversation: {conversation.id}, response_len={len(full_response)}")
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
    
    conversation_list = []
    for conv in conversations:
        last_msg_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        last_message = last_msg_result.scalar_one_or_none()
        
        msg_count_result = await db.execute(
            select(func.count(Message.id)).where(Message.conversation_id == conv.id)
        )
        message_count = msg_count_result.scalar() or 0
        
        conversation_list.append({
            "id": conv.id,
            "title": conv.title,
            "provider": conv.provider,
            "model": conv.model,
            "system_prompt": conv.system_prompt,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            "last_message": {
                "role": last_message.role,
                "content": last_message.content[:100] if last_message and len(last_message.content) > 100 else (last_message.content if last_message else None),
                "created_at": last_message.created_at.isoformat() if last_message and last_message.created_at else None,
            } if last_message else None,
            "message_count": message_count,
        })
    
    return conversation_list


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
    
    await db.delete(conversation)
    await db.commit()
    
    logger.info(f"[API] Deleted conversation: {conversation_id}")
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
    
    from app.langchain.services.chat import ChatService
    
    service = ChatService()
    
    message = f"Execute skill: {skill.name}\n\n{skill.prompt_template}"
    for key, value in request.parameters.items():
        message = message.replace(f"{{{key}}}", str(value))
    
    try:
        result = await service.chat(message, db=db)
        return {"result": result.output if hasattr(result, 'output') else result.get("output", "")}
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


@router.post("/skills/confirm-install")
async def confirm_skill_install(request: SkillInstallConfirmRequest):
    """
    用户确认安装技能依赖后，执行自动安装。
    返回 SSE 流推送安装进度（实时）。
    """
    from fastapi.responses import StreamingResponse
    import asyncio
    import json
    import os
    from pathlib import Path as _Path

    def _sse(data: dict) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    def _persist_env_vars(env_vars: dict):
        """将用户提供的环境变量同时写入 .env 文件持久化"""
        env_file = _Path("backend/.env")
        if not env_file.parent.exists():
            env_file = _Path(".env")

        existing = {}
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    existing[k.strip()] = v.strip()

        for key, value in env_vars.items():
            os.environ[key] = value
            existing[key] = value

        lines = [f"{k}={v}" for k, v in existing.items()]
        env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    async def install_stream():
        try:
            from app.core.managers import get_skill_manager
            from app.skills.dependency_resolver import DependencyResolver
            from app.skills.dependency_installer import DependencyInstaller

            skill_manager = get_skill_manager()
            if not skill_manager:
                yield _sse({"type": "error", "error": "SkillManager not initialized"})
                return

            if request.env_vars:
                _persist_env_vars(request.env_vars)
                yield _sse({
                    "type": "skill_install_progress",
                    "step": "env",
                    "detail": f"已配置 {len(request.env_vars)} 个环境变量并写入 .env",
                    "progress": 0.05,
                })

            skill = skill_manager.get_skill_by_slug(request.skill_slug)
            if not skill:
                try:
                    loaded = await skill_manager.install_skill_from_clawhub(
                        request.skill_slug, activate=False
                    )
                    if loaded:
                        skill = loaded
                except Exception:
                    pass
            if not skill:
                yield _sse({"type": "error", "error": f"Skill not found: {request.skill_slug}"})
                return

            yield _sse({
                "type": "skill_install_progress",
                "step": "check",
                "detail": f"正在检测 {skill.meta.name} 的依赖...",
                "progress": 0.1,
            })

            resolver = DependencyResolver()
            check = await resolver.check(skill)

            if check.satisfied:
                skill_manager.activate_skill(skill.meta.name)
                yield _sse({
                    "type": "skill_ready",
                    "skill_name": skill.meta.name,
                    "skill_slug": request.skill_slug,
                    "message": "所有依赖已满足，技能已激活！可以重新发送您的请求。",
                })
                return

            if not request.install_pip:
                check.missing_pip = []
            if not request.install_npm:
                check.missing_npm = []
            if not request.install_mcp:
                check.missing_mcp_servers = []
            if not request.install_bins:
                check.missing_bins = []

            installer = DependencyInstaller()

            # 使用 asyncio.Queue 实现实时进度推送
            progress_queue: asyncio.Queue = asyncio.Queue()
            _SENTINEL = object()

            async def progress_cb(step: str, detail: str, progress: float):
                await progress_queue.put({
                    "type": "skill_install_progress",
                    "step": step,
                    "detail": detail,
                    "progress": min(0.1 + progress * 0.85, 0.95),
                })

            async def _run_install():
                try:
                    result = await installer.install_all(
                        check, progress_callback=progress_cb, skill=skill
                    )
                    await progress_queue.put({"_result": result})
                except Exception as exc:
                    await progress_queue.put({"_error": str(exc)})
                finally:
                    await progress_queue.put(_SENTINEL)

            asyncio.create_task(_run_install())

            install_result = None
            install_error = None

            while True:
                item = await progress_queue.get()
                if item is _SENTINEL:
                    break
                if isinstance(item, dict):
                    if "_result" in item:
                        install_result = item["_result"]
                        continue
                    if "_error" in item:
                        install_error = item["_error"]
                        continue
                    yield _sse(item)

            if install_error:
                yield _sse({
                    "type": "skill_install_failed",
                    "skill_name": skill.meta.name,
                    "message": f"安装异常: {install_error}",
                })
            elif install_result and install_result.success:
                skill_manager.activate_skill(skill.meta.name)
                yield _sse({
                    "type": "skill_ready",
                    "skill_name": skill.meta.name,
                    "skill_slug": request.skill_slug,
                    "message": "所有依赖已安装完成，技能已激活！请重新发送您的请求以使用该技能。",
                    "details": install_result.to_dict(),
                })
            elif install_result:
                yield _sse({
                    "type": "skill_install_failed",
                    "skill_name": skill.meta.name,
                    "message": f"部分依赖安装失败: {', '.join(install_result.errors)}",
                    "details": install_result.to_dict(),
                })
            else:
                yield _sse({
                    "type": "skill_install_failed",
                    "skill_name": skill.meta.name,
                    "message": "安装过程未返回结果",
                })

        except Exception as e:
            logger.error(f"[API] confirm-install error: {e}")
            yield _sse({"type": "error", "error": str(e)})

    return StreamingResponse(install_stream(), media_type="text/event-stream")


# ==================== 自进化系统API端点 ====================

@router.get("/evolution/metrics")
async def get_evolution_metrics():
    """
    获取自进化系统指标
    
    Returns:
        EvolutionMetrics: 进化指标数据
    """
    from app.evolution import get_evolution_monitor
    
    monitor = get_evolution_monitor()
    return monitor.get_metrics().model_dump()


@router.post("/evolution/analyze")
async def trigger_evolution_analysis():
    """
    手动触发进化分析
    
    触发后台分析任务，识别模式并生成Skill
    
    Returns:
        dict: 分析状态
    """
    from app.evolution import get_evolution_monitor
    
    monitor = get_evolution_monitor()
    await monitor._analyze_and_evolve()
    
    return {"status": "analysis_triggered", "message": "进化分析已触发"}


@router.get("/evolution/patterns")
async def get_detected_patterns(days: int = 7):
    """
    获取识别的任务模式
    
    Args:
        days: 分析最近几天的数据
        
    Returns:
        dict: 识别的模式列表
    """
    from app.evolution.pattern_recognizer import PatternRecognizer
    
    recognizer = PatternRecognizer()
    patterns = await recognizer.analyze_recent_traces(days=days)
    
    return {
        "patterns": [p.model_dump() for p in patterns],
        "total": len(patterns),
        "days": days,
    }


@router.get("/evolution/skills")
async def list_evolved_skills():
    """
    列出自动生成的Skills
    
    Returns:
        dict: 自动生成的Skill列表
    """
    from pathlib import Path
    from app.evolution.config import evolution_settings
    
    skills_dir = Path(evolution_settings.SKILL_OUTPUT_DIR)
    skills = []
    
    if skills_dir.exists():
        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    skills.append({
                        "name": skill_dir.name,
                        "path": str(skill_dir),
                        "created": skill_md.stat().st_ctime,
                    })
    
    return {
        "skills": skills,
        "total": len(skills),
    }

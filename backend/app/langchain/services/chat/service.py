"""
Chat 服务

编排对话相关组件，提供统一的对话服务接口

职责：
1. 服务编排 - 协调 Memory、Prompts、Skills、Tools 等组件
2. 对话流程 - 实现完整的对话流程（构建提示词 -> LLM调用 -> 工具执行 -> 记忆存储）
3. 流式输出 - 支持流式对话
4. 记忆管理 - 短期/长期记忆存储和检索

不包含：
- Agent 概念（已移除）
- 记忆管理逻辑（委托给 memory 模块）
- 提示词构建逻辑（委托给 prompts 模块）
- 技能匹配逻辑（委托给 skills 模块）
"""
from typing import Optional, List, Any, Dict, AsyncIterator
from dataclasses import dataclass, field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from pathlib import Path
import uuid
import logging

from app.langchain.llm import get_llm
from app.langchain.tools import get_all_tools, get_tools_for_query
from app.langchain.memory import ShortTermMemory, LongTermMemory, MemorySummarizer
from app.langchain.prompts import PromptLoader, VariableInjector, PromptContext
from app.callbacks import AgentCallbackHandler, ExecutionTracer
from app.config import settings
from app.skills import DANGEROUS_TOOLS
from app.skills.tracer import get_skill_tracer, skill_trace_step
from app.core.managers import get_skill_manager
from app.langchain.services.stream_interrupt import (
    StreamInterruptManager,
    StreamInterruptedException,
    get_stream_interrupt_manager
)
from app.langchain.tracing.unified_tracer import (
    start_chat_trace,
    end_chat_trace,
    trace_step,
    memory_trace_step,
    skill_trace_step,
)

logger = logging.getLogger(__name__)


@dataclass
class ChatServiceConfig:
    """Chat 服务配置"""
    max_iterations: int = field(default_factory=lambda: settings.AGENT_MAX_ITERATIONS)
    max_history_turns: int = 10
    max_context_tokens: int = 4000
    enable_skills: bool = True
    enable_long_term_memory: bool = True
    # ClawHub 自动搜索与安装
    clawhub_auto_search: bool = field(default_factory=lambda: settings.CLAWHUB_AUTO_SEARCH)
    clawhub_auto_install: bool = field(default_factory=lambda: settings.CLAWHUB_AUTO_INSTALL)
    clawhub_min_confidence: float = field(default_factory=lambda: settings.CLAWHUB_MIN_CONFIDENCE)
    clawhub_search_limit: int = field(default_factory=lambda: settings.CLAWHUB_SEARCH_LIMIT)


@dataclass
class ChatResult:
    """对话结果"""
    output: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    trace: Optional[str] = None
    callback_summary: Optional[Dict] = None
    
    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)
    
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "output": self.output,
            "tool_calls": self.tool_calls,
            "trace": self.trace,
            "callback_summary": self.callback_summary,
        }


class ChatService:
    """
    Chat 服务
    
    编排对话相关组件，提供统一的对话服务接口
    
    使用方式：
        service = ChatService(conversation_id="conv_123")
        result = await service.chat("你好")
    """
    
    def __init__(
        self,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        user_name: str = "用户",
        agent_name: str = "智能助手",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        config: Optional[ChatServiceConfig] = None,
        short_term_memory: Optional[ShortTermMemory] = None,
        db_session: Optional[Any] = None,
        selected_tools: Optional[List[str]] = None,
    ):
        self.conversation_id = conversation_id
        self.user_id = user_id
        self.user_name = user_name
        self.agent_name = agent_name
        self.provider = provider
        self.model = model
        self.custom_system_prompt = system_prompt
        self.db_session = db_session
        self.config = config or ChatServiceConfig()
        
        self._llm: Optional[ChatOpenAI] = None
        self._tools: Optional[list] = None
        self._tools_by_name: Optional[dict] = None
        
        self._selected_tool_names = selected_tools
        self._tools_preselected = selected_tools is not None
        
        self.summarizer = MemorySummarizer(provider=provider, model=model)
        
        if short_term_memory is not None:
            self.short_term_memory = short_term_memory
            self._external_memory = True
        else:
            self.short_term_memory = ShortTermMemory(
                max_tokens=settings.MEMORY_MAX_TOKENS,
                summary_threshold=settings.MEMORY_SUMMARY_THRESHOLD,
                keep_recent_messages=settings.MEMORY_KEEP_RECENT,
                on_summary_needed=self._generate_summary,
                on_store_summary=self._store_summary_to_long_term,
            )
            self._external_memory = False
        
        self.long_term_memory = LongTermMemory(
            storage_path=settings.AGENT_MEMORY_PATH,
            chroma_path=settings.AGENT_VECTOR_PATH,
            embedding_model=settings.EMBEDDING_MODEL,
            reranker_model=settings.RERANKER_MODEL,
        )
        
        self.prompt_loader = PromptLoader(
            prompts_dir=str(Path(__file__).parent.parent.parent.parent.parent / "prompts"),
            enable_hot_reload=True,
        )
        
        self.injector = VariableInjector()
        self.prompt_context = PromptContext(self.injector)
        
        self.prompt_context.set_user_info(user_name)
        self.prompt_context.set_agent_info(agent_name)
        
        self._callback_handler: Optional[AgentCallbackHandler] = None
        self._tracer: Optional[ExecutionTracer] = None
        self._messages: List = []
        self._pending_skill_install: Optional[Dict[str, Any]] = None
        
        if self.config.enable_skills:
            # 使用全局单例（core.managers 负责创建和管理），确保所有组件共享同一实例
            self.skill_manager = get_skill_manager()
            logger.debug("[ChatService] 使用全局 SkillManager 单例")

            self._active_skill = None
            self._skills_initialized = False
        else:
            self.skill_manager = None
            self._active_skill = None
            self._skills_initialized = True
    
    @property
    def llm(self) -> ChatOpenAI:
        if self._llm is None:
            self._llm = get_llm(self.provider, self.model)
        return self._llm
    
    @property
    def tools(self) -> list:
        if self._tools is None:
            self._tools = get_all_tools()
        return self._tools
    
    async def _get_tools(self, query: str = "") -> list:
        """
        获取工具列表（支持预选和动态选择两种模式）

        - 预选模式：直接从 Registry 按名称加载（来自 LangGraph state）
        - 动态选择模式：通过 ToolSelector 按 query 关键词过滤后按需加载
        """
        if self._tools is not None:
            return self._tools

        if self._tools_preselected and self._selected_tool_names:
            from app.langchain.tools.registry import get_registry
            self._tools = await get_registry().get_tools_async(
                names=self._selected_tool_names
            )
            logger.info(
                f"[ChatService] Loaded {len(self._tools)} pre-selected tools "
                f"(requested: {len(self._selected_tool_names)})"
            )
        else:
            self._tools = await get_tools_for_query(query)
            logger.info(f"[ChatService] Loaded {len(self._tools)} tools via selector")

        return self._tools
    
    def set_selected_tools(self, tool_names: List[str]) -> None:
        """动态设置预选工具"""
        self._selected_tool_names = tool_names
        self._tools_preselected = True
        self._tools = None
        self._tools_by_name = None
    
    def set_extra_tools(self, tools: list):
        if self._tools is None:
            self._tools = get_all_tools()
        self._tools.extend(tools)
        self._tools_by_name = None

    # ------------------------------------------------------------------
    # 兼容别名：旧代码可能仍调用 _get_tools_with_mcp
    # ------------------------------------------------------------------
    async def _get_tools_with_mcp(self, query: str = "") -> list:
        return await self._get_tools(query)
    
    @property
    def tools_by_name(self) -> dict:
        if self._tools_by_name is None:
            self._tools_by_name = {tool.name: tool for tool in self.tools}
        return self._tools_by_name
    
    async def _generate_summary(self, messages: List) -> str:
        return await self.summarizer.summarize(messages)
    
    async def _store_summary_to_long_term(self, summary_content: str, message_count: int):
        try:
            await self.long_term_memory.store(
                content=summary_content,
                importance=4,
                category="summary",
                tags=["auto_summary", f"messages_{message_count}"],
                source_conversation_id=self.conversation_id,
            )
            logger.info(f"[ChatService] Summary synced to long-term memory: {message_count} messages")
        except Exception as e:
            logger.warning(f"Failed to sync summary to long-term memory: {e}")
    
    async def load_history_from_db(
        self,
        db_session: Optional[Any] = None,
        conversation_id: Optional[str] = None,
        limit: int = 20,
    ) -> int:
        session = db_session or self.db_session
        conv_id = conversation_id or self.conversation_id
        
        if not conv_id or not session:
            logger.warning("[ChatService] No conversation_id or db_session provided")
            return 0
        
        with memory_trace_step("load_history_from_db", "general", {
            "conversation_id": conv_id,
            "limit": limit,
        }):
            try:
                from sqlalchemy import select
                from app.langchain.models.database import Message
                
                result = await session.execute(
                    select(Message)
                    .where(Message.conversation_id == conv_id)
                    .order_by(Message.created_at.desc())
                    .limit(limit)
                )
                messages = list(reversed(result.scalars().all()))
                
                if not messages:
                    return 0
                
                loaded_count = 0
                for msg in messages:
                    if msg.role == "user":
                        self.short_term_memory.add_short_term_memory(HumanMessage(content=msg.content))
                    elif msg.role == "assistant":
                        self.short_term_memory.add_short_term_memory(AIMessage(content=msg.content))
                    elif msg.role == "system":
                        self.short_term_memory.add_short_term_memory(SystemMessage(content=msg.content))
                    loaded_count += 1
                
                logger.info(f"[ChatService] Loaded {loaded_count} history messages")
                return loaded_count
                
            except Exception as e:
                logger.error(f"[ChatService] Failed to load history: {e}")
                return 0
    
    async def _build_system_prompt(self, user_message: str) -> str:
        if self.custom_system_prompt:
            return self.custom_system_prompt
        
        # 确保工具已正确加载
        await self._get_tools(user_message)
        
        if not self._skills_initialized and self.skill_manager:
            await self.skill_manager.initialize()
            self.skill_manager.set_llm(self.llm)
            self._skills_initialized = True
        
        try:
            agent_template = await self.prompt_loader.load("agent")
            soul_template = await self.prompt_loader.load("soul")
            tools_template = await self.prompt_loader.load("tools")
        except FileNotFoundError as e:
            logger.warning(f"Prompt file not found: {e}")
            return self._get_default_system_prompt()
        
        if self.config.enable_long_term_memory:
            memory_context = await self.long_term_memory.get_long_term_memory_for_query(
                user_message,
                max_tokens=2000,
            )
            self.prompt_context.set_memory_context(memory_context or "暂无相关记忆")
        
        stats = self.short_term_memory.get_stats()
        self.injector.register_static("token_usage", stats.get("utilization", "0%"))
        
        summaries = self.short_term_memory.summaries
        if summaries:
            summary_text = summaries[-1].content if summaries else "暂无摘要"
            self.injector.register_static("short_term_summary", summary_text)
        else:
            self.injector.register_static("short_term_summary", "暂无对话摘要")
        
        # 工具描述通过 Function Calling (bind_tools) 传递给 LLM，无需再注入 System Prompt
        tool_count = len(self._tools) if self._tools else 0
        self.injector.register_static("available_tools", f"[{tool_count} 个工具已通过 Function Calling 注入]")
        
        if self.conversation_id:
            self.prompt_context.set_conversation_id(self.conversation_id)
        
        base_prompt = self.prompt_context.build(
            agent_template=agent_template,
            soul_template=soul_template,
            tools_template=tools_template,
        )
        
        if self.skill_manager:
            with skill_trace_step("skill_matching", {
                "user_message": user_message[:100] + "..." if len(user_message) > 100 else user_message,
                "tools_count": len(self.tools),
                "clawhub_auto_search": self.config.clawhub_auto_search,
            }):
                # 安全地提取工具名称（防止工具列表包含非Tool对象）
                available_tool_names = []
                for tool in self.tools:
                    if hasattr(tool, 'name'):
                        available_tool_names.append(tool.name)
                    else:
                        logger.warning(f"[ChatService] Tool 对象缺少 name 属性: {type(tool)}")

                # 优先使用带 ClawHub 降级的匹配（本地无匹配时自动搜索安装）
                if self.config.clawhub_auto_search:
                    match_result = await self.skill_manager.match_request_with_clawhub_fallback(
                        query=user_message,
                        available_tools=available_tool_names,
                        auto_install=self.config.clawhub_auto_install,
                        min_confidence=self.config.clawhub_min_confidence,
                        search_limit=self.config.clawhub_search_limit,
                    )
                else:
                    match_result = await self.skill_manager.match_request(
                        user_message,
                        available_tool_names,
                    )

            if match_result.is_skill_match and match_result.skill:
                # 检查是否有未满足的依赖
                if match_result.pending_dependencies and not match_result.pending_dependencies.satisfied:
                    self._pending_skill_install = {
                        "skill": match_result.skill,
                        "dependencies": match_result.pending_dependencies,
                    }
                    logger.info(
                        f"[ChatService] 技能 {match_result.skill.meta.name} 有未满足依赖，"
                        f"暂不注入提示词: {match_result.pending_dependencies.summary()}"
                    )
                    self._active_skill = None
                    return base_prompt

                self._active_skill = match_result.skill

                get_skill_tracer().trace("skill_activated", "service", {
                    "skill_name": match_result.skill.meta.name,
                    "confidence": match_result.confidence,
                    "reasoning": match_result.reasoning,
                    "via_clawhub": "[ClawHub" in match_result.reasoning,
                })

                skill_prompt = self.skill_manager.build_skill_prompt([match_result.skill])
                final_prompt = f"{base_prompt}\n\n{skill_prompt}"
                return final_prompt

        self._active_skill = None
        return base_prompt
    
    def _get_default_system_prompt(self) -> str:
        return f"""你是{self.agent_name}，一个智能助手。

当前用户：{self.user_name}
当前时间：{self._get_current_time()}

你可以使用工具来帮助用户解决问题。请根据用户需求选择最合适的方式。"""
    
    def _get_current_time(self) -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _get_chat_history(self) -> List:
        return self.short_term_memory.get_context()
    
    def _create_callback_handler(self) -> AgentCallbackHandler:
        self._callback_handler = AgentCallbackHandler(
            conversation_id=self.conversation_id
        )
        return self._callback_handler
    
    async def _execute_tool(self, tool_name: str, tool_args: dict) -> str:
        tool = self.tools_by_name.get(tool_name)
        if not tool:
            available_tools = list(self.tools_by_name.keys())
            return f"工具 '{tool_name}' 不存在。可用的工具: {', '.join(available_tools[:10])}..."
        
        if tool_name in DANGEROUS_TOOLS:
            return f"⚠️ 工具 '{tool_name}' 被标记为危险工具（{DANGEROUS_TOOLS[tool_name]}），需要特殊权限才能执行。"
        
        if self._active_skill and self.skill_manager:
            allowed, reason = self.skill_manager.check_tool_permission(
                tool_name, self._active_skill
            )
            if not allowed:
                return f"权限不足: {reason}"
        
        if not tool_args:
            tool_schema = getattr(tool, 'args_schema', None)
            if tool_schema:
                required_fields = []
                schema = tool_schema.model_json_schema()
                for field_name, field_info in schema.get('properties', {}).items():
                    if field_name in schema.get('required', []):
                        required_fields.append(field_name)
                if required_fields:
                    return f"工具 '{tool_name}' 缺少必需参数。需要提供: {', '.join(required_fields)}"
        
        try:
            if hasattr(tool, "ainvoke"):
                result = await tool.ainvoke(tool_args)
            elif hasattr(tool, "invoke"):
                result = tool.invoke(tool_args)
            elif hasattr(tool, "func"):
                import asyncio
                if asyncio.iscoroutinefunction(tool.func):
                    result = await tool.func(**tool_args)
                else:
                    result = tool.func(**tool_args)
            else:
                return f"工具 '{tool_name}' 无法执行，请尝试其他方式完成任务。"
            
            self._record_tool_call(tool_name, tool_args, result)
            
            return result
        except TypeError as e:
            return f"工具 '{tool_name}' 参数错误: {str(e)}。请检查参数格式。"
        except FileNotFoundError as e:
            return f"文件操作失败: {str(e)}"
        except PermissionError as e:
            return f"权限错误: {str(e)}"
        except Exception as e:
            return f"执行 '{tool_name}' 时出错: {str(e)}"
    
    def _record_tool_call(self, tool_name: str, tool_args: dict, result: str) -> None:
        args_str = str(tool_args)
        if len(args_str) > 100:
            args_str = args_str[:100] + "..."
        
        result_str = str(result)
        if len(result_str) > 200:
            result_str = result_str[:200] + "..."
        
        tool_summary = f"[工具调用] {tool_name}({args_str}) → {result_str}"
        
        self.short_term_memory.add_short_term_memory(SystemMessage(content=tool_summary))
        
        logger.info(f"[ChatService] Tool call recorded: {tool_name}")
    
    async def chat(
        self,
        message: str,
        db: Optional[Any] = None,
        max_iterations: Optional[int] = None,
        history_messages: Optional[List] = None,
    ) -> ChatResult:
        max_iterations = max_iterations or self.config.max_iterations
        self._tracer = ExecutionTracer(f"chat_{self.conversation_id or 'default'}")
        self._tracer.start()
        callback = self._create_callback_handler()
        
        ctx = start_chat_trace(self.conversation_id or "default")
        
        try:
            with trace_step("load_tools", {"message_len": len(message)}):
                await self._get_tools(message)

            with trace_step("build_system_prompt", {"conversation_id": self.conversation_id}):
                system_prompt = await self._build_system_prompt(message)

            with trace_step("build_context", {"history_turns": len(self._get_chat_history())}):
                self._messages = [SystemMessage(content=system_prompt)]

                if history_messages:
                    self._messages.extend(history_messages)
                else:
                    self._messages.extend(self._get_chat_history())

                self._messages.append(HumanMessage(content=message))

            llm_with_tools = self.llm.bind_tools(self.tools)

            all_tool_calls = []

            self._tracer.step("chat_execution")
            
            for iteration in range(max_iterations):
                callback.on_llm_start({}, [str(self._messages[-1].content)])
                
                response = await llm_with_tools.ainvoke(
                    self._messages,
                    config={"callbacks": [callback]},
                )
                
                self._messages.append(response)
                callback.on_llm_end(response)
                
                if not response.tool_calls:
                    await self._finalize_conversation(message, response.content or "")
                    
                    self._tracer.step("completed")
                    
                    end_chat_trace(output=response.content[:100] if response.content else None)
                    
                    return ChatResult(
                        output=response.content,
                        tool_calls=all_tool_calls if all_tool_calls else None,
                        trace=self._tracer.get_report(),
                        callback_summary=callback.get_summary(),
                    )
                
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    tool_id = tool_call.get("id", "")
                    
                    all_tool_calls.append({
                        "name": tool_name,
                        "arguments": tool_args,
                    })
                    
                    callback.on_tool_start({"name": tool_name}, str(tool_args))
                    
                    with trace_step("tool_execution", {"tool_name": tool_name, "args": str(tool_args)[:100]}):
                        result = await self._execute_tool(tool_name, tool_args)
                    
                    callback.on_tool_end(result, name=tool_name)
                    
                    self._messages.append(ToolMessage(
                        content=str(result),
                        tool_call_id=tool_id,
                    ))
            
            self._tracer.step("max_iterations_reached")
            
            end_chat_trace(error="Max iterations reached")
            
            return ChatResult(
                output="达到最大迭代次数，任务未完成",
                tool_calls=all_tool_calls,
                trace=self._tracer.get_report(),
                callback_summary=callback.get_summary(),
            )
            
        except Exception as e:
            self._tracer.error(e)
            end_chat_trace(error=str(e))
            raise
    
    async def chat_stream(
        self,
        message: str,
        db: Optional[Any] = None,
        max_iterations: Optional[int] = None,
        session_id: Optional[str] = None,
        history_messages: Optional[List] = None,
    ) -> AsyncIterator[dict]:
        max_iterations = max_iterations or self.config.max_iterations
        self._tracer = ExecutionTracer(f"chat_stream_{self.conversation_id or 'default'}")
        self._tracer.start()
        callback = self._create_callback_handler()
        
        interrupt_manager = get_stream_interrupt_manager()
        
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        await interrupt_manager.create_session(session_id, self.conversation_id)
        
        ctx = start_chat_trace(self.conversation_id or "default")
        
        logger.info(f"[ChatService] chat_stream start: message_len={len(message)}, session_id={session_id}")
        
        try:
            with trace_step("load_tools", {"message_len": len(message)}):
                await self._get_tools(message)
            logger.info(f"[ChatService] Loaded {len(self.tools)} tools")
            
            with trace_step("build_system_prompt", {"conversation_id": self.conversation_id}):
                self._pending_skill_install = None
                system_prompt = await self._build_system_prompt(message)
            logger.info(f"[ChatService] System prompt built: len={len(system_prompt)}")

            # 如果有待确认的技能依赖，发送确认事件给前端，然后停止（不调用 LLM）
            if self._pending_skill_install:
                skill = self._pending_skill_install["skill"]
                dep_check = self._pending_skill_install["dependencies"]
                yield {
                    "type": "skill_dependency_confirm",
                    "skill_name": skill.meta.name,
                    "skill_slug": getattr(skill, '_clawhub_slug', '') or skill.meta.name.lower().replace(' ', '-'),
                    "missing": dep_check.to_dict(),
                    "message": (
                        f"技能 '{skill.meta.name}' 需要安装以下依赖才能正常使用，"
                        f"是否继续？\n{dep_check.summary()}"
                    ),
                }
                self._tracer.step("pending_skill_dependency")
                end_chat_trace(output="waiting_for_skill_dependency_confirm")
                yield {
                    "type": "done",
                    "content": "",
                }
                return

            with trace_step("build_context", {"history_turns": len(self._get_chat_history())}):
                self._messages = [SystemMessage(content=system_prompt)]
                
                if history_messages:
                    self._messages.extend(history_messages)
                else:
                    self._messages.extend(self._get_chat_history())
                
                self._messages.append(HumanMessage(content=message))
            logger.info(f"[ChatService] Context built: total_messages={len(self._messages)}")
            
            llm_with_tools = self.llm.bind_tools(self.tools)
            
            full_content = ""
            
            self._tracer.step("chat_streaming")
            
            for iteration in range(max_iterations):
                logger.info(f"[ChatService] Starting iteration {iteration + 1}/{max_iterations}")
                
                if await interrupt_manager.is_interrupted(session_id):
                    yield {
                        "type": "interrupted",
                        "content": full_content,
                        "message": "用户中断了输出",
                    }
                    return
                
                iteration_content = ""
                tool_calls_by_index = {}
                
                with trace_step("llm_stream", {"iteration": iteration + 1}):
                    async for chunk in llm_with_tools.astream(
                        self._messages,
                        config={"callbacks": [callback]},
                    ):
                        if await interrupt_manager.is_interrupted(session_id):
                            yield {
                                "type": "interrupted",
                                "content": full_content,
                                "message": "用户中断了输出",
                            }
                            return
                        
                        if chunk.content:
                            iteration_content += chunk.content
                            full_content += chunk.content
                            yield {
                                "type": "content",
                                "content": chunk.content,
                            }
                        
                        if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                            for tc_chunk in chunk.tool_call_chunks:
                                tc_index = tc_chunk.get("index", 0)
                                tc_id = tc_chunk.get("id")
                                
                                if tc_index not in tool_calls_by_index:
                                    tool_calls_by_index[tc_index] = {
                                        "id": tc_id or "",
                                        "name": "",
                                        "args": "",
                                    }
                                
                                if tc_id:
                                    tool_calls_by_index[tc_index]["id"] = tc_id
                                
                                if tc_chunk.get("name"):
                                    tool_calls_by_index[tc_index]["name"] += tc_chunk["name"]
                                
                                if tc_chunk.get("args"):
                                    args_str = tc_chunk["args"]
                                    if isinstance(args_str, str):
                                        tool_calls_by_index[tc_index]["args"] += args_str
                                    else:
                                        tool_calls_by_index[tc_index]["args"] += str(args_str)
                
                ai_message = AIMessage(content=iteration_content)
                
                if tool_calls_by_index:
                    import json
                    tool_calls = []
                    for tc_index in sorted(tool_calls_by_index.keys()):
                        tc_data = tool_calls_by_index[tc_index]
                        if tc_data["name"]:
                            try:
                                args = json.loads(tc_data["args"]) if tc_data["args"] else {}
                            except:
                                args = {}
                            tool_calls.append({
                                "id": tc_data["id"] or f"call_{tc_index}",
                                "name": tc_data["name"],
                                "args": args,
                            })
                    ai_message.tool_calls = tool_calls
                
                self._messages.append(ai_message)
                
                if not ai_message.tool_calls:
                    logger.info(f"[ChatService] No tool calls, finalizing response: content_len={len(full_content)}")
                    
                    await self._finalize_conversation(message, full_content)
                    
                    self._tracer.step("completed")
                    
                    end_chat_trace(output=full_content[:100] if full_content else None)
                    
                    yield {
                        "type": "done",
                        "content": full_content,
                        "trace": self._tracer.get_report(),
                    }
                    return
                
                logger.info(f"[ChatService] Tool calls detected: {[tc['name'] for tc in ai_message.tool_calls]}")
                
                for tool_call in ai_message.tool_calls:
                    if await interrupt_manager.is_interrupted(session_id):
                        yield {
                            "type": "interrupted",
                            "content": full_content,
                            "message": "用户中断了输出",
                        }
                        return
                    
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    tool_id = tool_call.get("id", "")
                    
                    logger.info(f"[ChatService] Executing tool: {tool_name}, args={str(tool_args)[:100]}")
                    
                    yield {
                        "type": "tool_call",
                        "name": tool_name,
                        "arguments": tool_args,
                    }
                    
                    callback.on_tool_start({"name": tool_name}, str(tool_args))
                    
                    with trace_step("tool_execution", {"tool_name": tool_name, "args": str(tool_args)[:100]}):
                        result = await self._execute_tool(tool_name, tool_args)
                    
                    logger.info(f"[ChatService] Tool result: {tool_name} -> {str(result)[:200]}...")
                    
                    callback.on_tool_end(result, name=tool_name)
                    
                    yield {
                        "type": "tool_result",
                        "name": tool_name,
                        "result": str(result)[:500],
                    }
                    
                    self._messages.append(ToolMessage(
                        content=str(result),
                        tool_call_id=tool_id,
                    ))
            
            logger.warning(f"[ChatService] Max iterations reached: {max_iterations}")
            self._tracer.step("max_iterations_reached")
            
            end_chat_trace(error="Max iterations reached")
            
            yield {
                "type": "done",
                "content": full_content or "达到最大迭代次数，任务未完成",
                "trace": self._tracer.get_report(),
            }
            
        except StreamInterruptedException as e:
            logger.warning(f"[ChatService] Stream interrupted: {e}")
            end_chat_trace(error=str(e))
            yield {
                "type": "interrupted",
                "content": full_content,
                "message": str(e),
            }
        except Exception as e:
            logger.error(f"[ChatService] Error in chat_stream: {e}")
            self._tracer.error(e)
            end_chat_trace(error=str(e))
            yield {
                "type": "error",
                "error": str(e),
            }
        finally:
            await interrupt_manager.remove_session(session_id)
            logger.info(f"[ChatService] chat_stream end: session_id={session_id}")
    
    async def _finalize_conversation(self, user_message: str, assistant_response: str):
        with memory_trace_step("finalize_conversation", "general", {
            "user_msg_len": len(user_message),
            "assistant_msg_len": len(assistant_response),
        }):
            self.short_term_memory.add_short_term_memory(HumanMessage(content=user_message))
            self.short_term_memory.add_short_term_memory(AIMessage(content=assistant_response))
            
            if self.short_term_memory.needs_summary:
                logger.info(f"[ChatService] Summary threshold reached, triggering summary")
                summary = await self.short_term_memory.check_and_summarize()
                if summary:
                    logger.info(f"[ChatService] Summary generated: {summary.token_count} tokens")
        
        if self.config.enable_long_term_memory:
            await self._store_to_long_term(user_message, assistant_response)
    
    async def _store_to_long_term(self, user_message: str, assistant_response: str):
        try:
            content = f"用户: {user_message}\n助手: {assistant_response}"
            
            similar = await self.long_term_memory.retrieve(content, top_k=3)
            if similar and similar[0][1] > 0.95:
                logger.info("Similar memory exists, skipping storage")
                return
            
            importance = await self.summarizer.assess_importance(content)
            
            if importance < 3:
                logger.info(f"Memory importance too low ({importance}), skipping storage")
                return
            
            key_info = await self.summarizer.extract_key_info(content)
            
            await self.long_term_memory.store(
                content=content,
                importance=importance,
                category="conversation",
                tags=key_info if key_info else None,
                source_conversation_id=self.conversation_id,
            )
            
            logger.info(f"Stored to long-term memory: importance={importance}, tags={key_info}")
            
        except Exception as e:
            logger.warning(f"Failed to store to long-term memory: {e}")
    
    def get_memory_stats(self) -> dict:
        return {
            "short_term": self.short_term_memory.get_stats(),
        }
    
    async def get_long_term_stats(self) -> dict:
        return await self.long_term_memory.get_stats()
    
    def clear_short_term_memory(self) -> None:
        self.short_term_memory.clear()
    
    async def start_prompt_watcher(self):
        await self.prompt_loader.start_watcher()
    
    async def stop_prompt_watcher(self):
        await self.prompt_loader.stop_watcher()
    
    async def reload_prompts(self):
        self.prompt_loader.clear_cache()
    
    def get_last_trace(self) -> Optional[dict]:
        if self._tracer:
            return self._tracer.get_report()
        return None
    
    def get_last_callback_summary(self) -> Optional[dict]:
        if self._callback_handler:
            return self._callback_handler.get_summary()
        return None

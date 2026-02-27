from typing import Optional, List, Dict, Any
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
import asyncio
import uuid
import logging
from app.langchain.llm import get_llm
from app.langchain.agents.main_agent import MainAgent
from app.langchain.agents.researcher_agent import ResearcherAgent
from app.langchain.agents.rag_agent import RagAgent
from app.langchain.services.supervisor import IntentClassifier, QueryIntent, IntentResult, KBRouter
from app.langchain.services.rag import ConversationTurn, RewrittenQuery, QueryRewriteConfig
from app.db.session import get_async_session
from app.langchain.agents.stream_interrupt import (
    StreamInterruptManager,
    get_stream_interrupt_manager
)
from app.langchain.tracing.rag_trace import (
    start_rag_trace,
    end_rag_trace,
    get_rag_trace,
    trace_step,
)


class RouteResult(BaseModel):
    """路由执行结果"""
    route: str
    result: Any
    confidence: float
    source: str
    execution_time_ms: float


class ResultSelector:
    """
    结果选择器
    
    从多个并行路由结果中选择最佳结果
    """
    
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
    
    async def select_best_result(
        self,
        query: str,
        results: List[RouteResult],
    ) -> RouteResult:
        """
        选择最佳结果
        
        策略：
        1. 优先选择高置信度结果
        2. 如果置信度相近，使用 LLM 判断
        3. 考虑结果完整性和相关性
        """
        if not results:
            return None
        
        if len(results) == 1:
            return results[0]
        
        results.sort(key=lambda x: x.confidence, reverse=True)
        
        top_results = results[:3]
        
        if len(top_results) == 1:
            return top_results[0]
        
        if top_results[0].confidence - top_results[1].confidence > 0.1:
            return top_results[0]
        
        return await self._llm_select(query, top_results)
    
    async def _llm_select(
        self,
        query: str,
        results: List[RouteResult],
    ) -> RouteResult:
        """使用 LLM 选择最佳结果"""
        
        options_text = "\n".join([
            f"[{i}] {r.route} (置信度: {r.confidence:.2f}, 来源: {r.source})"
            f"    结果预览: {str(r.result)[:200]}..."
            for i, r in enumerate(results)
        ])
        
        prompt = f"""用户问题：{query}

有多个候选结果，请选择最合适的一个：

候选结果：
{options_text}

请返回JSON格式：
{{
    "best_index": 0,
    "reasoning": "选择理由"
}}

只返回JSON，不要其他内容。"""

        try:
            response = await self.llm.ainvoke(prompt)
            
            import json
            content = response.content.strip()
            if content.startswith("```"):
                content = content.strip("`").strip()
                if content.startswith("json"):
                    content = content[4:].strip()
            
            result = json.loads(content)
            best_index = result.get("best_index", 0)
            
            if 0 <= best_index < len(results):
                return results[best_index]
            
            return results[0]
            
        except Exception:
            return results[0]


class SupervisorAgent:
    """
    Supervisor Agent
    
    职责：
    1. 接收用户请求
    2. 意图识别与路由决策
    3. 协调多个Agent协作
    4. 支持并行路由
    5. 结果整合与返回
    """
    
    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        db_session=None,
    ):
        self.llm = get_llm(provider, model)
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.db_session = db_session
        
        self.main_agent = MainAgent(
            provider=provider,
            model=model,
            conversation_id=conversation_id,
        )
        
        self.researcher_agent = ResearcherAgent(llm=self.llm)
        
        self.rag_agent = RagAgent(
            llm=self.llm,
            user_id=user_id,
            db_session=db_session,
        )
        
        self.intent_classifier = IntentClassifier(llm=self.llm, db_session=db_session)
        self.result_selector = ResultSelector(llm=self.llm)
        self._kb_router = None
    
    @property
    def kb_router(self):
        if self._kb_router is None and self.db_session is not None:
            self._kb_router = KBRouter(db=self.db_session)
        return self._kb_router
    
    async def chat(self, message: str, db=None) -> dict:
        """
        主对话入口
        """
        if db is None:
            async for session in get_async_session():
                db = session
                break
        
        self.db_session = db
        self.rag_agent.db_session = db
        self.intent_classifier.db_session = db
        
        intent_result = await self.intent_classifier.classify_with_alternatives(message)
        
        routes = self._decide_routes(intent_result)
        
        if len(routes) > 1:
            return await self._parallel_route(message, intent_result, routes, db)
        else:
            return await self._single_route(message, routes[0], intent_result, db)
    
    def _decide_routes(self, intent_result: IntentResult) -> List[str]:
        """
        路由决策
        
        Returns:
            路由列表，如果多个路由，则执行并行路由
        """
        routes = []
        primary_route = self._get_route(intent_result.intent)
        logging.info(f"Primary route: {primary_route}")
        routes.append(primary_route)
        
        parallel_threshold = 0.65
        
        if intent_result.confidence < parallel_threshold:
            for secondary in intent_result.secondary_intents:
                route = secondary.get("route", "direct")
                if route not in routes:
                    routes.append(route)
        
        return routes
    
    def _get_route(self, intent: QueryIntent) -> str:
        """将意图转换为路由"""
        route_map = {
            QueryIntent.KB_QUERY: "rag_first",
            QueryIntent.SEARCH_TASK: "research_first",
            QueryIntent.DOCUMENT_TASK: "tool_first",
            QueryIntent.DATA_ANALYSIS: "tool_first",
            QueryIntent.CODE_TASK: "direct",
            QueryIntent.TOOL_TASK: "direct",
            QueryIntent.GENERAL_CHAT: "direct",
            QueryIntent.AMBIGUOUS: "parallel",
        }
        return route_map.get(intent, "direct")
    
    async def _single_route(
        self,
        message: str,
        route: str,
        intent_result: IntentResult,
        db=None,
    ) -> dict:
        """单路由执行"""
        
        if route == "rag_first":
            return await self._rag_enhanced_chat(message, intent_result, db)
        elif route == "research_first":
            return await self._research_enhanced_chat(message, db)
        elif route == "tool_first":
            return await self._tool_enhanced_chat(message, db)
        else:
            return await self._direct_chat(message, db)
    
    async def _parallel_route(
        self,
        message: str,
        intent_result: IntentResult,
        routes: List[str],
        db=None,
    ) -> dict:
        """
        并行路由执行
        
        同时执行多个路由，选择最佳结果
        """
        tasks = []
        
        for route in routes:
            if route == "rag_first":
                tasks.append(("rag_first", self._rag_route_task(message, intent_result, db)))
            elif route == "research_first":
                tasks.append(("research_first", self._research_route_task(message, db)))
            elif route == "tool_first":
                tasks.append(("tool_first", self._tool_route_task(message, db)))
            elif route == "direct":
                tasks.append(("direct", self._direct_route_task(message, db)))
        
        results = await asyncio.gather(*[task for _, task in tasks])
        
        route_results = []
        for (route_name, _), result in zip(tasks, results):
            route_results.append(RouteResult(
                route=route_name,
                result=result.get("result", ""),
                confidence=result.get("confidence", 0.5),
                source=result.get("source", "unknown"),
                execution_time_ms=result.get("execution_time_ms", 0),
            ))
        
        best_result = await self.result_selector.select_best_result(message, route_results)
        
        return {
            "output": best_result.result,
            "route": best_result.route,
            "confidence": best_result.confidence,
            "parallel_routes": [r.route for r in route_results],
        }
    
    async def _rag_route_task(self, message: str, intent_result: IntentResult, db=None) -> dict:
        """RAG路由任务"""
        import time
        start_time = time.time()
        
        try:
            result = await self._rag_enhanced_chat(message, intent_result, db)
            execution_time = (time.time() - start_time) * 1000
            
            return {
                "result": result.get("output", ""),
                "confidence": 0.8,
                "source": "rag",
                "execution_time_ms": execution_time,
            }
        except Exception as e:
            return {
                "result": f"RAG路由失败: {str(e)}",
                "confidence": 0.0,
                "source": "rag",
                "execution_time_ms": 0,
            }
    
    async def _research_route_task(self, message: str, db=None) -> dict:
        """搜索路由任务"""
        import time
        start_time = time.time()
        
        try:
            result = await self._research_enhanced_chat(message, db)
            execution_time = (time.time() - start_time) * 1000
            
            return {
                "result": result.get("output", ""),
                "confidence": 0.75,
                "source": "research",
                "execution_time_ms": execution_time,
            }
        except Exception as e:
            return {
                "result": f"搜索路由失败: {str(e)}",
                "confidence": 0.0,
                "source": "research",
                "execution_time_ms": 0,
            }
    
    async def _tool_route_task(self, message: str, db=None) -> dict:
        """工具路由任务"""
        import time
        start_time = time.time()
        
        try:
            result = await self._tool_enhanced_chat(message, db)
            execution_time = (time.time() - start_time) * 1000
            
            return {
                "result": result.get("output", ""),
                "confidence": 0.85,
                "source": "tool",
                "execution_time_ms": execution_time,
            }
        except Exception as e:
            return {
                "result": f"工具路由失败: {str(e)}",
                "confidence": 0.0,
                "source": "tool",
                "execution_time_ms": 0,
            }
    
    async def _direct_route_task(self, message: str, db=None) -> dict:
        """直接路由任务"""
        import time
        start_time = time.time()
        
        try:
            result = await self._direct_chat(message, db)
            execution_time = (time.time() - start_time) * 1000
            
            return {
                "result": result.get("output", ""),
                "confidence": 0.7,
                "source": "direct",
                "execution_time_ms": execution_time,
            }
        except Exception as e:
            return {
                "result": f"直接路由失败: {str(e)}",
                "confidence": 0.0,
                "source": "direct",
                "execution_time_ms": 0,
            }
    
    async def _rag_enhanced_chat(
        self,
        message: str,
        intent_result: IntentResult,
        db=None,
    ) -> dict:
        """
        RAG增强对话 - 简化版
        
        RagAgent 负责完整的 RAG 流程，SupervisorAgent 只负责协调
        """
        kb_ids = intent_result.kb_hints
        
        if kb_ids and self.kb_router:
            from app.knowledge_base.services.permission import PermissionService
            permission_service = PermissionService(self.db_session)
            kb_ids = await self.kb_router.route(
                query=message,
                user_id=self.user_id,
                permission_service=permission_service,
                kb_hints=kb_ids,
            )
            logging.info(f"[SupervisorAgent] KBRouter resolved kb_ids: {kb_ids}")
        
        rag_result = await self.rag_agent.chat_with_rag(
            query=message,
            kb_ids=kb_ids,
            top_k=5,
        )
        
        if rag_result.formatted_context:
            enhanced_message = f"{rag_result.formatted_context}\n\n用户问题：{message}"
        else:
            enhanced_message = message
        
        result = await self.main_agent.chat(enhanced_message, db=db)
        
        self.rag_agent.add_assistant_message(result.get("output", ""))
        
        return {
            "output": result.get("output", ""),
            "sources": [
                {
                    "kb_name": r.kb_name,
                    "doc_name": r.doc_name,
                    "score": r.score,
                    "chunk_id": r.chunk_id,
                }
                for r in rag_result.sources[:5]
            ],
            "rewritten_query": rag_result.rewritten_query,
            "entities": rag_result.entities,
        }
    
    async def _research_enhanced_chat(self, message: str, db=None) -> dict:
        """
        搜索增强对话
        """
        research_result = await self.researcher_agent.research(message)
        enhanced_message = f"{message}\n\n[搜索结果]\n{research_result}"
        
        return await self.main_agent.chat(enhanced_message, db=db)
    
    async def _tool_enhanced_chat(self, message: str, db=None) -> dict:
        """
        工具增强对话
        """
        tool_hint = "\n\n提示：此任务可能需要使用文档操作工具（如创建Word/Excel/PPT文档）或数据分析工具。"
        enhanced_message = f"{message}{tool_hint}"
        
        return await self.main_agent.chat(enhanced_message, db=db)
    
    async def _direct_chat(self, message: str, db=None) -> dict:
        """
        直接对话
        """
        return await self.main_agent.chat(message, db=db)
    
    def _build_rag_context(self, results: List) -> str:
        """构建RAG上下文"""
        context_parts = ["【知识库检索结果】"]
        context_parts.append("以下是从知识库中检索到的相关信息，请参考这些内容回答用户问题：\n")
        
        for i, r in enumerate(results[:3], 1):
            context_parts.append(
                f"[{i}] 来源：{r.kb_name} > {r.doc_name}\n"
                f"    相关度：{r.score:.2f}\n"
                f"    内容：{r.content[:500]}{'...' if len(r.content) > 500 else ''}\n"
            )
        
        return "\n".join(context_parts)
    
    async def chat_stream(self, message: str, db=None, session_id: Optional[str] = None):
        """
        流式对话入口
        """
        if db is None:
            async for session in get_async_session():
                db = session
                break
        
        self.db_session = db
        self.rag_agent.db_session = db
        self.intent_classifier.db_session = db
        
        start_rag_trace(message)
        
        logging.info(f"[SupervisorAgent] chat_stream start: message='{message[:50]}...'")
        
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        self._current_session_id = session_id
        
        intent_result = await self.intent_classifier.classify_with_alternatives(message)
        
        routes = self._decide_routes(intent_result)
        
        logging.info(f"[SupervisorAgent] Intent: {intent_result.intent.value}, Confidence: {intent_result.confidence}")
        logging.info(f"[SupervisorAgent] Routes: {routes}")
        
        if len(routes) > 1:
            async for chunk in self._parallel_route_stream(message, intent_result, routes, db, session_id):
                yield chunk
        else:
            async for chunk in self._single_route_stream(message, routes[0], intent_result, db, session_id):
                yield chunk
    
    async def _single_route_stream(
        self,
        message: str,
        route: str,
        intent_result: IntentResult,
        db=None,
        session_id: Optional[str] = None,
    ):
        """单路由流式执行"""
        logging.info(f"[SupervisorAgent] Executing route: {route}")
        
        if route == "rag_first":
            logging.info(f"[SupervisorAgent] Calling RagAgent.chat_with_rag_stream()")
            async for chunk in self._rag_enhanced_chat_stream(message, intent_result, db, session_id):
                yield chunk
        elif route == "research_first":
            async for chunk in self._research_enhanced_chat_stream(message, db, session_id):
                yield chunk
        elif route == "tool_first":
            async for chunk in self._tool_enhanced_chat_stream(message, db, session_id):
                yield chunk
        else:
            async for chunk in self._direct_chat_stream(message, db, session_id):
                yield chunk
    
    async def _parallel_route_stream(
        self,
        message: str,
        intent_result: IntentResult,
        routes: List[str],
        db=None,
        session_id: Optional[str] = None,
    ):
        """
        并行路由流式执行
        
        简化版本：选择第一个路由执行流式输出
        """
        primary_route = routes[0]
        
        yield {
            "type": "route_info",
            "routes": routes,
            "primary": primary_route,
        }
        
        async for chunk in self._single_route_stream(message, primary_route, intent_result, db, session_id):
            yield chunk
    
    async def _rag_enhanced_chat_stream(
        self,
        message: str,
        intent_result: IntentResult,
        db=None,
        session_id: Optional[str] = None,
    ):
        """
        RAG增强流式对话 - 简化版
        
        RagAgent 负责完整的 RAG 流程，SupervisorAgent 只负责协调
        """
        kb_ids = intent_result.kb_hints
        
        if kb_ids and self.kb_router:
            from app.knowledge_base.services.permission import PermissionService
            permission_service = PermissionService(self.db_session)
            kb_ids = await self.kb_router.route(
                query=message,
                user_id=self.user_id,
                permission_service=permission_service,
                kb_hints=kb_ids,
            )
            logging.info(f"[SupervisorAgent] KBRouter resolved kb_ids: {kb_ids}")
        
        with trace_step("rag_agent_retrieval", {"query": message, "kb_hints": kb_ids}):
            formatted_context = None
            async for event in self.rag_agent.chat_with_rag_stream(
                query=message,
                kb_ids=kb_ids,
                top_k=5,
            ):
                if event["type"] == "rag_context":
                    formatted_context = event["formatted_context"]
                else:
                    yield event
        
        logging.info(f"[SupervisorAgent] RAG formatted_context length: {len(formatted_context) if formatted_context else 0}")
        logging.info(f"[SupervisorAgent] RAG formatted_context preview: {formatted_context[:500] if formatted_context else 'None'}...")
        
        if formatted_context:
            enhanced_message = f"{formatted_context}\n\n用户问题：{message}"
        else:
            enhanced_message = message
        
        logging.info(f"[SupervisorAgent] Enhanced message length: {len(enhanced_message)}")
        logging.info(f"[SupervisorAgent] Enhanced message preview: {enhanced_message[:800]}...")
        
        with trace_step("main_agent_generation", {
            "enhanced_message_len": len(enhanced_message),
            "has_context": formatted_context is not None,
            "context_len": len(formatted_context) if formatted_context else 0,
        }):
            async for chunk in self.main_agent.chat_stream(enhanced_message, db=db, session_id=session_id):
                yield chunk
    
    async def _research_enhanced_chat_stream(self, message: str, db=None, session_id: Optional[str] = None):
        """
        搜索增强流式对话
        """
        with trace_step("research_agent_search", {"query": message}):
            research_result = await self.researcher_agent.research(message)
        
        logging.info(f"[SupervisorAgent] Research result length: {len(research_result) if research_result else 0}")
        logging.info(f"[SupervisorAgent] Research result preview: {research_result[:500] if research_result else 'None'}...")
        
        enhanced_message = f"{message}\n\n[搜索结果]\n{research_result}"
        
        with trace_step("main_agent_generation", {
            "enhanced_message_len": len(enhanced_message),
            "has_research": bool(research_result),
        }):
            async for chunk in self.main_agent.chat_stream(enhanced_message, db=db, session_id=session_id):
                yield chunk
    
    async def _tool_enhanced_chat_stream(self, message: str, db=None, session_id: Optional[str] = None):
        """
        工具增强流式对话
        """
        tool_hint = "\n\n提示：此任务可能需要使用文档操作工具（如创建Word/Excel/PPT文档）或数据分析工具。"
        enhanced_message = f"{message}{tool_hint}"
        
        logging.info(f"[SupervisorAgent] Tool-enhanced message length: {len(enhanced_message)}")
        
        with trace_step("main_agent_generation", {
            "enhanced_message_len": len(enhanced_message),
            "route_type": "tool_first",
        }):
            async for chunk in self.main_agent.chat_stream(enhanced_message, db=db, session_id=session_id):
                yield chunk
    
    async def _direct_chat_stream(self, message: str, db=None, session_id: Optional[str] = None):
        """
        直接流式对话
        """
        logging.info(f"[SupervisorAgent] Direct chat message length: {len(message)}")
        
        with trace_step("main_agent_generation", {
            "message_len": len(message),
            "route_type": "direct",
        }):
            async for chunk in self.main_agent.chat_stream(message, db=db, session_id=session_id):
                yield chunk

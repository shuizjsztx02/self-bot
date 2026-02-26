from typing import Optional, List, Dict, Any
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
import asyncio
import uuid

from app.langchain.llm import get_llm
from app.langchain.agents.main_agent import MainAgent
from app.langchain.agents.researcher_agent import ResearcherAgent
from app.langchain.agents.rag_agent import RagAgent
from app.langchain.routers.intent_classifier import IntentClassifier, QueryIntent, IntentResult
from app.langchain.routers.kb_router import KBRouter
from app.langchain.routers.multi_turn_rag import (
    MultiTurnRAGManager,
    MultiTurnRAGConfig,
    MultiTurnRAGPipeline,
)
from app.db.session import get_async_session
from app.langchain.agents.stream_interrupt import (
    StreamInterruptManager,
    get_stream_interrupt_manager
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
        
        self.intent_classifier = IntentClassifier(llm=self.llm)
        self.result_selector = ResultSelector(llm=self.llm)
        self._kb_router = None
        self._multi_turn_rag_manager = None
        self._multi_turn_rag_pipeline = None
    
    @property
    def kb_router(self):
        if self._kb_router is None and self.db_session is not None:
            self._kb_router = KBRouter(db=self.db_session)
        return self._kb_router
    
    @property
    def multi_turn_rag(self) -> MultiTurnRAGManager:
        """
        获取多轮对话RAG管理器（懒加载）
        """
        if self._multi_turn_rag_manager is None:
            from app.knowledge_base.services.search import SearchService
            from app.knowledge_base.services.embedding import EmbeddingService
            from app.core.token_counter import TokenCounter
            
            config = MultiTurnRAGConfig(
                max_history_turns=10,
                max_context_tokens=4000,
                max_retrieved_docs=10,
                min_relevance_score=0.3,
                enable_query_rewrite=True,
                enable_compression=True,
                enable_attribution=True,
                enable_query_expansion=True,
            )
            
            self._multi_turn_rag_manager = MultiTurnRAGManager(
                config=config,
                token_counter=TokenCounter(),
                embedding_service=EmbeddingService(),
                search_service=None,
                llm_client=self.llm,
            )
        
        return self._multi_turn_rag_manager
    
    def _get_search_service(self, db):
        """获取搜索服务"""
        from app.knowledge_base.services.search import SearchService
        return SearchService(db)
    
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
        RAG增强对话（使用MultiTurnRAGManager）
        
        功能：
        1. 查询重写 - 处理依赖上下文的查询
        2. 查询扩展 - 生成查询变体
        3. 混合检索 - 向量+BM25
        4. 上下文压缩 - 控制Token预算
        5. 引用溯源 - 追踪来源
        """
        kb_ids = None
        if intent_result.kb_hints:
            kb_ids = intent_result.kb_hints
        
        manager = self.multi_turn_rag
        
        if db:
            manager.search_service = self._get_search_service(db)
        
        async def generate_response(query: str, context: str) -> str:
            if context:
                enhanced_message = f"{context}\n\n用户问题：{query}"
            else:
                enhanced_message = query
            
            result = await self.main_agent.chat(enhanced_message, db=db)
            return result.get("output", "")
        
        rag_response = await manager.chat_with_rag(
            query=message,
            kb_ids=kb_ids,
            top_k=5,
            generate_response=generate_response,
        )
        
        return {
            "output": rag_response.answer,
            "sources": [
                {
                    "kb_name": s.kb_name,
                    "doc_name": s.doc_name,
                    "score": s.score,
                    "chunk_id": s.chunk_id,
                }
                for s in rag_response.sources
            ],
            "rewritten_query": rag_response.rewritten_query,
            "confidence": rag_response.overall_confidence,
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
        
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        self._current_session_id = session_id
        
        intent_result = await self.intent_classifier.classify_with_alternatives(message)
        
        routes = self._decide_routes(intent_result)
        
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
        
        if route == "rag_first":
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
        RAG增强流式对话（使用MultiTurnRAGManager）
        
        功能：
        1. 查询重写
        2. 混合检索
        3. 上下文压缩
        4. 流式生成回答
        """
        kb_ids = None
        if intent_result.kb_hints:
            kb_ids = intent_result.kb_hints
        
        manager = self.multi_turn_rag
        
        if db:
            manager.search_service = self._get_search_service(db)
        
        retrieval_result = await manager.process_query(
            query=message,
            kb_ids=kb_ids,
            top_k=5,
        )
        
        yield {
            "type": "rag_info",
            "rewritten_query": retrieval_result.rewritten_query,
            "query_variations": retrieval_result.query_variations,
            "entities": retrieval_result.entities,
            "doc_count": len(retrieval_result.documents),
        }
        
        if retrieval_result.documents:
            yield {
                "type": "rag_sources",
                "sources": [
                    {
                        "kb_name": getattr(d, 'kb_name', ''),
                        "doc_name": getattr(d, 'doc_name', ''),
                        "score": getattr(d, 'score', 0),
                    }
                    for d in retrieval_result.documents[:5]
                ],
            }
        
        if retrieval_result.formatted_context:
            enhanced_message = f"{retrieval_result.formatted_context}\n\n用户问题：{message}"
        else:
            enhanced_message = message
        
        async for chunk in self.main_agent.chat_stream(enhanced_message, db=db, session_id=session_id):
            yield chunk
        
        manager.add_user_message(message)
        
        if retrieval_result.rewritten_query != message:
            manager.history_manager.update_last_user_message(
                original=message,
                rewritten=retrieval_result.rewritten_query,
            )
    
    async def _research_enhanced_chat_stream(self, message: str, db=None, session_id: Optional[str] = None):
        """
        搜索增强流式对话
        """
        research_result = await self.researcher_agent.research(message)
        enhanced_message = f"{message}\n\n[搜索结果]\n{research_result}"
        
        async for chunk in self.main_agent.chat_stream(enhanced_message, db=db, session_id=session_id):
            yield chunk
    
    async def _tool_enhanced_chat_stream(self, message: str, db=None, session_id: Optional[str] = None):
        """
        工具增强流式对话
        """
        tool_hint = "\n\n提示：此任务可能需要使用文档操作工具（如创建Word/Excel/PPT文档）或数据分析工具。"
        enhanced_message = f"{message}{tool_hint}"
        
        async for chunk in self.main_agent.chat_stream(enhanced_message, db=db, session_id=session_id):
            yield chunk
    
    async def _direct_chat_stream(self, message: str, db=None, session_id: Optional[str] = None):
        """
        直接流式对话
        """
        async for chunk in self.main_agent.chat_stream(message, db=db, session_id=session_id):
            yield chunk

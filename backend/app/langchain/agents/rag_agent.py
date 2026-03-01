from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from dataclasses import dataclass, field as dataclass_field
import logging

from app.langchain.llm import get_llm
from app.knowledge_base.schemas import SearchResult, RAGSearchInput
from app.langchain.tracing.rag_trace import get_rag_trace, trace_step

logger = logging.getLogger(__name__)


@dataclass
class RagAgentConfig:
    """RagAgent 配置"""
    max_history_turns: int = 10
    max_context_tokens: int = 4000
    max_retrieved_docs: int = 10
    top_k: int = 5
    use_hybrid: bool = True
    use_rerank: bool = True
    hybrid_alpha: float = 0.5
    enable_query_rewrite: bool = True
    enable_query_expansion: bool = True


@dataclass
class RagProcessResult:
    """查询处理结果"""
    query: str
    rewritten_query: str
    query_variations: List[str]
    entities: List[str]
    documents: List[SearchResult]
    formatted_context: str
    
    @classmethod
    def empty(cls, query: str) -> "RagProcessResult":
        return cls(
            query=query,
            rewritten_query=query,
            query_variations=[],
            entities=[],
            documents=[],
            formatted_context="",
        )


@dataclass
class RagChatResult:
    """RAG 对话结果"""
    query: str
    rewritten_query: str
    formatted_context: str
    sources: List[SearchResult]
    entities: List[str]


class RagAgent:
    """
    RAG知识库Agent - 完整版
    
    职责：
    1. 查询增强 - 重写、扩展、实体提取
    2. 对话上下文管理 - 多轮对话上下文
    3. 知识库检索 - 权限检查 + 混合检索
    4. 上下文压缩 - Token 预算控制
    5. 结果格式化 - 生成 RAG 上下文
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        user_id: Optional[str] = None,
        db_session=None,
        config: Optional[RagAgentConfig] = None,
        short_term_memory=None,
    ):
        self._llm = llm
        self.user_id = user_id
        self.db_session = db_session
        self.config = config or RagAgentConfig()
        
        self._short_term_memory = short_term_memory
        
        self._search_service = None
        self._permission_service = None
        self._kb_service = None
        
        self._query_rewriter = None
        self._context_compressor = None
    
    def _get_llm(self) -> ChatOpenAI:
        if self._llm is None:
            self._llm = get_llm()
        return self._llm
    
    async def _get_services(self):
        """懒加载所有服务"""
        if self._search_service is None:
            from app.knowledge_base.services import SearchService, PermissionService, KnowledgeBaseService
            from app.knowledge_base.services.embedding import EmbeddingService
            from app.knowledge_base.vector_store import VectorStoreFactory
            from app.db.session import get_async_session
            from app.langchain.services.rag.query_rewriter import QueryRewriter
            from app.langchain.services.rag.rag_types import QueryRewriteConfig
            from app.knowledge_base.services.compression import ContextCompressor, CompressionConfig
            
            if self.db_session is None:
                async for session in get_async_session():
                    self.db_session = session
                    break
            
            vector_store = VectorStoreFactory.create("chroma")
            embedding_service = EmbeddingService()
            
            self._search_service = SearchService(
                vector_store=vector_store,
                embedding_service=embedding_service,
            )
            self._permission_service = PermissionService(self.db_session)
            self._kb_service = KnowledgeBaseService(self.db_session, vector_store)
            
            self._query_rewriter = QueryRewriter(
                config=QueryRewriteConfig(
                    max_history_turns=self.config.max_history_turns,
                    enable_query_expansion=self.config.enable_query_expansion,
                ),
                llm_client=self._llm,
            )
            
            self._context_compressor = ContextCompressor(
                config=CompressionConfig(
                    max_tokens=self.config.max_context_tokens,
                    max_documents=self.config.max_retrieved_docs,
                ),
                embedding_service=embedding_service,
            )
    
    async def process_query(
        self,
        query: str,
        kb_ids: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> RagProcessResult:
        """
        完整的查询处理流程
        
        流程：
        1. 查询重写（代词解析 + LLM 重写）
        2. 查询扩展（生成变体）
        3. 权限检查
        4. 多查询检索
        5. 结果合并去重
        6. 上下文压缩
        7. 格式化输出
        """
        await self._get_services()
        
        if self._short_term_memory:
            history = self._short_term_memory.get_history_as_turns(
                limit=self.config.max_history_turns
            )
        else:
            history = []
        
        with trace_step("query_rewrite", {"query": query, "history_len": len(history)}):
            if self.config.enable_query_rewrite:
                rewrite_result = await self._query_rewriter.rewrite(query, history)
            else:
                from app.langchain.services.rag.rag_types import RewrittenQuery
                rewrite_result = RewrittenQuery(
                    original_query=query,
                    rewritten_query=query,
                )
        
        all_queries = [rewrite_result.rewritten_query] + rewrite_result.variations
        
        if not kb_ids:
            logger.info(f"[RagAgent] No kb_ids provided, fetching all available knowledge bases")
            all_kbs = await self._kb_service.list_all(is_active=True)
            kb_ids = [kb.id for kb in all_kbs]
            logger.info(f"[RagAgent] Found {len(kb_ids)} available knowledge bases: {kb_ids}")
        
        if not kb_ids:
            logger.warning(f"[RagAgent] No knowledge bases available for search")
            return RagProcessResult.empty(query)
        
        with trace_step("multi_query_search", {"queries": all_queries, "kb_ids": kb_ids}):
            all_results = await self._multi_query_search(all_queries, kb_ids, top_k)
        
        with trace_step("metadata_fill", {"results_count": len(all_results)}):
            await self._fill_metadata(all_results)
        
        conversation_context = ""
        if self._short_term_memory:
            conversation_context = self._short_term_memory.get_context_summary(
                max_tokens=self.config.max_context_tokens // 4
            )
        
        with trace_step("context_compress", {"docs_count": len(all_results)}):
            formatted_context = await self._compress_context(
                rewrite_result.rewritten_query,
                all_results,
                conversation_context,
            )
        
        logger.info(f"[RagAgent] Process complete: {len(all_results)} docs, context_len={len(formatted_context)}")
        
        return RagProcessResult(
            query=query,
            rewritten_query=rewrite_result.rewritten_query,
            query_variations=rewrite_result.variations,
            entities=rewrite_result.extracted_entities,
            documents=all_results,
            formatted_context=formatted_context,
        )
    
    async def _multi_query_search(
        self,
        queries: List[str],
        kb_ids: List[str],
        top_k: int,
    ) -> List[SearchResult]:
        """多查询检索，合并去重"""
        logger.info(f"[RagAgent] _multi_query_search: queries={queries}, kb_ids={kb_ids}, top_k={top_k}")
        
        all_results = []
        seen_ids = set()
        
        for i, query in enumerate(queries):
            logger.info(f"[RagAgent] Searching query {i+1}/{len(queries)}: '{query[:50]}...'")
            
            if self.config.use_hybrid:
                results = await self._search_service.cross_hybrid_search(
                    kb_ids=kb_ids,
                    query=query,
                    top_k=top_k,
                    alpha=self.config.hybrid_alpha,
                    use_rerank=self.config.use_rerank,
                    deduplicate=False,
                )
            else:
                results = await self._search_service.cross_search(
                    kb_ids=kb_ids,
                    query=query,
                    top_k=top_k,
                    use_rerank=self.config.use_rerank,
                )
            
            logger.info(f"[RagAgent] Query '{query[:30]}...' found {len(results)} results")
            
            for r in results:
                if r.chunk_id not in seen_ids:
                    seen_ids.add(r.chunk_id)
                    all_results.append(r)
        
        all_results.sort(key=lambda x: x.score, reverse=True)
        logger.info(f"[RagAgent] Total results: {len(all_results)} (before dedup), {len(all_results[:self.config.max_retrieved_docs])} (after dedup)")
        
        return all_results[:self.config.max_retrieved_docs]
    
    async def _compress_context(
        self,
        query: str,
        documents: List[SearchResult],
        conversation_context: str,
    ) -> str:
        """压缩上下文"""
        if not documents:
            return ""
        
        formatted_context, _ = await self._context_compressor.compress_with_context(
            query=query,
            documents=documents,
            conversation_context=conversation_context,
            max_tokens=self.config.max_context_tokens,
        )
        
        return formatted_context
    
    async def _fill_metadata(self, results: List[SearchResult]) -> None:
        """填充 kb_name 和 doc_name"""
        for result in results:
            kb = await self._kb_service.get_by_id(result.kb_id)
            if kb:
                result.kb_name = kb.name
            
            from app.knowledge_base.models import Document
            from sqlalchemy import select
            doc_result = await self.db_session.execute(
                select(Document).where(Document.id == result.doc_id)
            )
            doc = doc_result.scalar_one_or_none()
            if doc:
                result.doc_name = doc.filename
    
    async def chat_with_rag(
        self,
        query: str,
        kb_ids: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> RagChatResult:
        """
        完整的 RAG 对话流程
        
        包含：
        - 查询处理
        - 历史更新
        - 返回结构化结果
        """
        process_result = await self.process_query(query, kb_ids, top_k)
        
        if self._short_term_memory:
            self._short_term_memory.add_short_term_memory(HumanMessage(content=query))
        
        return RagChatResult(
            query=query,
            rewritten_query=process_result.rewritten_query,
            formatted_context=process_result.formatted_context,
            sources=process_result.documents,
            entities=process_result.entities,
        )
    
    async def chat_with_rag_stream(
        self,
        query: str,
        kb_ids: Optional[List[str]] = None,
        top_k: int = 5,
    ):
        """流式版本的 RAG 对话"""
        logger.info(f"[RagAgent] chat_with_rag_stream start: query='{query[:50]}...', kb_ids={kb_ids}")
        await self._get_services()
        
        if self._short_term_memory:
            history = self._short_term_memory.get_history_as_turns(
                limit=self.config.max_history_turns
            )
        else:
            history = []
        logger.info(f"[RagAgent] History length: {len(history)}")
        
        if self.config.enable_query_rewrite:
            logger.info(f"[RagAgent] Query rewrite enabled, calling rewriter")
            rewrite_result = await self._query_rewriter.rewrite(query, history)
            logger.info(f"[RagAgent] Rewrite result: original='{query[:30]}...', rewritten='{rewrite_result.rewritten_query[:30]}...', variations={len(rewrite_result.variations)}")
        else:
            from app.langchain.services.rag.rag_types import RewrittenQuery
            rewrite_result = RewrittenQuery(
                original_query=query,
                rewritten_query=query,
            )
            logger.info(f"[RagAgent] Query rewrite disabled, using original query")
        
        yield {
            "type": "rag_info",
            "rewritten_query": rewrite_result.rewritten_query,
            "query_variations": rewrite_result.variations,
            "entities": rewrite_result.extracted_entities,
        }
        
        logger.info(f"[RagAgent] Calling process_query")
        process_result = await self.process_query(query, kb_ids, top_k)
        logger.info(f"[RagAgent] process_query complete: {len(process_result.documents)} docs, context_len={len(process_result.formatted_context)}")
        
        if process_result.documents:
            logger.info(f"[RagAgent] Yielding rag_sources with {min(len(process_result.documents), 5)} sources")
            yield {
                "type": "rag_sources",
                "sources": [
                    {
                        "kb_name": r.kb_name,
                        "doc_name": r.doc_name,
                        "score": r.score,
                    }
                    for r in process_result.documents[:5]
                ],
            }
        else:
            logger.warning(f"[RagAgent] No documents found for query")
        
        if self._short_term_memory:
            self._short_term_memory.add_short_term_memory(HumanMessage(content=query))
        
        yield {
            "type": "rag_context",
            "formatted_context": process_result.formatted_context,
        }
        
        logger.info(f"[RagAgent] chat_with_rag_stream complete")
    
    def add_assistant_message(self, content: str):
        """添加助手消息到共享 memory"""
        if self._short_term_memory:
            self._short_term_memory.add_short_term_memory(AIMessage(content=content))
    
    async def search(
        self,
        query: str,
        kb_ids: Optional[List[str]] = None,
        top_k: int = 5,
        use_rerank: bool = True,
        use_hybrid: bool = True,
        hybrid_alpha: float = 0.5,
    ) -> List[SearchResult]:
        """
        执行知识库检索（纯检索，不包含查询增强）
        
        职责分离：
        - 知识库获取：本方法处理（无kb_ids时获取所有可用知识库）
        - 检索逻辑：委托给 SearchService
        - 元数据填充：本方法处理
        """
        await self._get_services()
        
        if not kb_ids:
            logger.info(f"[RagAgent.search] No kb_ids provided, fetching all available knowledge bases")
            all_kbs = await self._kb_service.list_all(is_active=True)
            kb_ids = [kb.id for kb in all_kbs]
            logger.info(f"[RagAgent.search] Found {len(kb_ids)} available knowledge bases")
        
        if not kb_ids:
            logger.warning(f"[RagAgent.search] No knowledge bases available for search")
            return []
        
        if use_hybrid and hasattr(self._search_service, 'cross_hybrid_search'):
            results = await self._search_service.cross_hybrid_search(
                kb_ids=kb_ids,
                query=query,
                top_k=top_k,
                alpha=hybrid_alpha,
                use_rerank=use_rerank,
                deduplicate=True,
            )
        else:
            results = await self._search_service.cross_search(
                kb_ids=kb_ids,
                query=query,
                top_k=top_k,
                use_rerank=use_rerank,
            )
        
        await self._fill_metadata(results)
        
        return results
    
    async def get_rag_context(
        self,
        query: str,
        kb_ids: Optional[List[str]] = None,
        top_k: int = 5,
        min_score: float = 0.5,
    ) -> str:
        """
        获取RAG上下文文本
        用于注入到MainAgent的prompt中
        """
        results = await self.search(query, kb_ids, top_k)
        
        relevant_results = [r for r in results if r.score >= min_score]
        
        if not relevant_results:
            return ""
        
        context_parts = ["【知识库检索结果】"]
        context_parts.append("以下是从知识库中检索到的相关信息：\n")
        
        for i, result in enumerate(relevant_results, 1):
            context_parts.append(
                f"[{i}] 来源：{result.kb_name} > {result.doc_name}\n"
                f"    相关度：{result.score:.2f}\n"
                f"    内容：{result.content[:500]}{'...' if len(result.content) > 500 else ''}\n"
            )
        
        return "\n".join(context_parts)
    
    def as_tool(self) -> StructuredTool:
        """
        封装为工具供其他Agent调用
        """
        
        async def run_rag_search(
            query: str,
            kb_ids: Optional[List[str]] = None,
            top_k: int = 5,
        ) -> str:
            results = await self.search(query, kb_ids, top_k)
            
            if not results:
                return "未找到相关信息"
            
            return self._format_results(results)
        
        return StructuredTool(
            name="rag_search",
            description="""知识库检索工具。用于从内部知识库中检索相关信息。

适用场景：
- 查询公司制度、流程、规定
- 查询产品文档、使用手册
- 查询技术文档、API文档
- 查询项目资料、方案文档

输入：检索查询和可选的知识库ID列表
输出：相关的知识库内容片段""",
            args_schema=RAGSearchInput,
            func=lambda query, kb_ids=None, top_k=5: None,
            coroutine=run_rag_search,
        )
    
    def _format_results(self, results: List[SearchResult]) -> str:
        """格式化检索结果"""
        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(
                f"[{i}] 来源：{r.kb_name}/{r.doc_name}\n"
                f"    相关度：{r.score:.2f}\n"
                f"    内容：{r.content[:500]}{'...' if len(r.content) > 500 else ''}\n"
            )
        return "\n".join(formatted)

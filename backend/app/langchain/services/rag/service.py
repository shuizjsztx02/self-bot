"""
RAG 服务

编排 RAG 相关组件，提供统一的检索服务接口

职责：
1. 服务编排 - 协调 QueryRewriter、ContextManager、SearchService 等组件
2. 检索流程 - 实现完整的检索流程（重写 -> 检索 -> 压缩 -> 格式化）
3. 结果格式化 - 生成结构化的检索结果

不包含：
- Agent 概念（已移除）
- 查询重写逻辑（委托给 query_rewriter.py）
- 上下文管理逻辑（委托给 context_manager.py）
- 压缩逻辑（委托给 knowledge_base/services/compression.py）
"""
from typing import Optional, List, Any, Dict, AsyncIterator
from dataclasses import dataclass, field
from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage, AIMessage
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.langchain.tracing.unified_tracer import (
    start_rag_trace,
    end_rag_trace,
    trace_step,
    get_trace,
)
from app.langchain.services.rag.query_rewriter import QueryRewriter
from app.langchain.services.rag.context_manager import ContextManager
from app.langchain.services.rag.rag_types import (
    RewrittenQuery,
    QueryRewriteConfig,
    ConversationTurn,
)
from app.knowledge_base.schemas import SearchResult, RAGSearchInput

logger = logging.getLogger(__name__)


@dataclass
class RagServiceConfig:
    """RAG 服务配置"""
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
class RagSearchResult:
    """检索结果"""
    query: str
    rewritten_query: str
    documents: List[SearchResult]
    formatted_context: str


class RagService:
    """
    RAG 服务
    
    编排 RAG 相关组件，提供统一的检索服务接口
    
    使用方式：
        service = RagService(db_session=db_session)
        result = await service.process_query("用户问题")
    
    支持共享记忆：
        service = RagService(short_term_memory=shared_memory)
    """
    
    def __init__(
        self,
        db_session: Optional[AsyncSession] = None,
        user_id: Optional[str] = None,
        config: Optional[RagServiceConfig] = None,
        llm_client: Optional[Any] = None,
        context_manager: Optional[ContextManager] = None,
        short_term_memory: Optional[Any] = None,
    ):
        self.db_session = db_session
        self.user_id = user_id
        self.config = config or RagServiceConfig()
        self._llm_client = llm_client
        
        self._context_manager = context_manager
        self._short_term_memory = short_term_memory
        
        self._search_service = None
        self._kb_service = None
        self._embedding_service = None
        self._context_compressor = None
        self._query_rewriter = None
    
    async def _ensure_services(self) -> None:
        """确保所有依赖服务已初始化"""
        if self._search_service is not None:
            return
        
        from app.knowledge_base.services import SearchService, KnowledgeBaseService
        from app.knowledge_base.services.embedding import EmbeddingService
        from app.knowledge_base.vector_store import VectorStoreFactory
        from app.knowledge_base.services.compression import ContextCompressor, CompressionConfig
        from app.db.session import get_async_session
        
        if self.db_session is None:
            async for session in get_async_session():
                self.db_session = session
                break
        
        vector_store = VectorStoreFactory.create("chroma")
        self._embedding_service = EmbeddingService()
        
        self._search_service = SearchService(
            vector_store=vector_store,
            embedding_service=self._embedding_service,
        )
        
        self._kb_service = KnowledgeBaseService(self.db_session, vector_store)
        
        self._context_compressor = ContextCompressor(
            config=CompressionConfig(
                max_tokens=self.config.max_context_tokens,
                max_documents=self.config.max_retrieved_docs,
            ),
            embedding_service=self._embedding_service,
        )
        
        self._query_rewriter = QueryRewriter(
            config=QueryRewriteConfig(
                max_history_turns=self.config.max_history_turns,
                enable_query_expansion=self.config.enable_query_expansion,
            ),
            llm_client=self._llm_client,
        )
    
    def _get_context_manager(self) -> ContextManager:
        """获取上下文管理器"""
        if self._context_manager is None:
            self._context_manager = ContextManager(
                max_turns=self.config.max_history_turns,
                max_tokens=self.config.max_context_tokens,
            )
        return self._context_manager
    
    async def process_query(
        self,
        query: str,
        kb_ids: Optional[List[str]] = None,
        top_k: Optional[int] = None,
        history: Optional[List[ConversationTurn]] = None,
    ) -> RagProcessResult:
        """
        完整的查询处理流程
        
        流程：
        1. 查询重写（代词解析 + LLM 重写）
        2. 查询扩展（生成变体）
        3. 多查询检索
        4. 结果合并去重
        5. 上下文压缩
        6. 格式化输出
        
        Args:
            query: 用户查询
            kb_ids: 知识库 ID 列表（可选）
            top_k: 每个查询返回的文档数
            history: 对话历史（可选）
        
        Returns:
            RagProcessResult: 处理结果
        """
        await self._ensure_services()
        
        top_k = top_k or self.config.top_k
        
        ctx = start_rag_trace(query)
        
        try:
            if history is None:
                context_manager = self._get_context_manager()
                history = context_manager.get_history(limit=self.config.max_history_turns)
            
            with trace_step("query_rewrite", {"query": query, "history_len": len(history)}):
                if self.config.enable_query_rewrite:
                    rewrite_result = await self._query_rewriter.rewrite(query, history)
                else:
                    rewrite_result = RewrittenQuery(
                        original_query=query,
                        rewritten_query=query,
                    )
            
            all_queries = [rewrite_result.rewritten_query] + rewrite_result.variations
            
            if not kb_ids:
                all_kbs = await self._kb_service.list_all(is_active=True)
                kb_ids = [kb.id for kb in all_kbs]
                logger.info(f"[RagService] Found {len(kb_ids)} available knowledge bases")
            
            if not kb_ids:
                logger.warning("[RagService] No knowledge bases available")
                return RagProcessResult.empty(query)
            
            with trace_step("multi_query_search", {"queries": all_queries, "kb_ids": kb_ids}):
                all_results = await self._multi_query_search(all_queries, kb_ids, top_k)
            
            with trace_step("metadata_fill", {"results_count": len(all_results)}):
                await self._fill_metadata(all_results)
            
            conversation_context = ""
            if history:
                conversation_context = self._format_history_context(history)
            
            with trace_step("context_compress", {"docs_count": len(all_results)}):
                formatted_context = await self._compress_context(
                    rewrite_result.rewritten_query,
                    all_results,
                    conversation_context,
                )
            
            logger.info(f"[RagService] Process complete: {len(all_results)} docs, context_len={len(formatted_context)}")
            
            result = RagProcessResult(
                query=query,
                rewritten_query=rewrite_result.rewritten_query,
                query_variations=rewrite_result.variations,
                entities=rewrite_result.extracted_entities,
                documents=all_results,
                formatted_context=formatted_context,
            )
            
            end_rag_trace(output=formatted_context[:100] if formatted_context else None)
            
            return result
            
        except Exception as e:
            end_rag_trace(error=str(e))
            raise
    
    async def _multi_query_search(
        self,
        queries: List[str],
        kb_ids: List[str],
        top_k: int,
    ) -> List[SearchResult]:
        """多查询检索，合并去重"""
        all_results = []
        seen_ids = set()
        
        for i, query in enumerate(queries):
            logger.info(f"[RagService] Searching query {i+1}/{len(queries)}: '{query[:50]}...'")
            
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
            
            for r in results:
                if r.chunk_id not in seen_ids:
                    seen_ids.add(r.chunk_id)
                    all_results.append(r)
        
        all_results.sort(key=lambda x: x.score, reverse=True)
        
        return all_results[:self.config.max_retrieved_docs]
    
    async def _fill_metadata(self, results: List[SearchResult]) -> None:
        """填充 kb_name 和 doc_name"""
        for result in results:
            try:
                kb = await self._kb_service.get_by_id(result.kb_id)
                if kb:
                    result.kb_name = kb.name
                
                if self.db_session:
                    from app.knowledge_base.models import Document
                    from sqlalchemy import select
                    doc_result = await self.db_session.execute(
                        select(Document).where(Document.id == result.doc_id)
                    )
                    doc = doc_result.scalar_one_or_none()
                    if doc:
                        result.doc_name = doc.filename
            except Exception as e:
                logger.debug(f"Failed to fill metadata: {e}")
    
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
    
    def _format_history_context(self, history: List[ConversationTurn]) -> str:
        """格式化对话历史"""
        if not history:
            return ""
        
        parts = []
        for turn in history[-5:]:
            prefix = "用户" if turn.role == "user" else "助手"
            parts.append(f"{prefix}: {turn.content}")
        
        return "\n".join(parts)
    
    async def search(
        self,
        query: str,
        kb_ids: Optional[List[str]] = None,
        top_k: Optional[int] = None,
    ) -> RagSearchResult:
        """
        执行知识库检索（简化版，不包含查询增强）
        
        Args:
            query: 查询文本
            kb_ids: 知识库 ID 列表
            top_k: 返回文档数
        
        Returns:
            RagSearchResult: 检索结果
        """
        await self._ensure_services()
        
        top_k = top_k or self.config.top_k
        
        if not kb_ids:
            all_kbs = await self._kb_service.list_all(is_active=True)
            kb_ids = [kb.id for kb in all_kbs]
        
        if not kb_ids:
            return RagSearchResult(
                query=query,
                rewritten_query=query,
                documents=[],
                formatted_context="",
            )
        
        if self.config.use_hybrid:
            results = await self._search_service.cross_hybrid_search(
                kb_ids=kb_ids,
                query=query,
                top_k=top_k,
                alpha=self.config.hybrid_alpha,
                use_rerank=self.config.use_rerank,
                deduplicate=True,
            )
        else:
            results = await self._search_service.cross_search(
                kb_ids=kb_ids,
                query=query,
                top_k=top_k,
                use_rerank=self.config.use_rerank,
            )
        
        await self._fill_metadata(results)
        
        formatted_context = await self._compress_context(query, results, "")
        
        return RagSearchResult(
            query=query,
            rewritten_query=query,
            documents=results,
            formatted_context=formatted_context,
        )
    
    async def get_context(
        self,
        query: str,
        kb_ids: Optional[List[str]] = None,
        top_k: Optional[int] = None,
        min_score: float = 0.5,
    ) -> str:
        """
        获取 RAG 上下文文本
        
        用于注入到 prompt 中
        
        Args:
            query: 查询文本
            kb_ids: 知识库 ID 列表
            top_k: 返回文档数
            min_score: 最小相关性分数
        
        Returns:
            格式化的上下文文本
        """
        result = await self.search(query, kb_ids, top_k)
        
        relevant_docs = [d for d in result.documents if d.score >= min_score]
        
        if not relevant_docs:
            return ""
        
        context_parts = ["【知识库检索结果】"]
        context_parts.append("以下是从知识库中检索到的相关信息：\n")
        
        for i, doc in enumerate(relevant_docs, 1):
            kb_name = getattr(doc, 'kb_name', '未知知识库')
            doc_name = getattr(doc, 'doc_name', '未知文档')
            context_parts.append(
                f"[{i}] 来源：{kb_name} > {doc_name}\n"
                f"    相关度：{doc.score:.2f}\n"
                f"    内容：{doc.content[:500]}{'...' if len(doc.content) > 500 else ''}\n"
            )
        
        return "\n".join(context_parts)
    
    async def process_stream(
        self,
        query: str,
        kb_ids: Optional[List[str]] = None,
        top_k: Optional[int] = None,
        history: Optional[List[ConversationTurn]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        流式处理查询
        
        Yields:
            处理过程中的中间状态
        """
        await self._ensure_services()
        
        top_k = top_k or self.config.top_k
        
        logger.info(f"[RagService] process_stream start: query='{query[:50]}...'")
        
        if history is None:
            context_manager = self._get_context_manager()
            history = context_manager.get_history(limit=self.config.max_history_turns)
        
        if self.config.enable_query_rewrite:
            rewrite_result = await self._query_rewriter.rewrite(query, history)
        else:
            rewrite_result = RewrittenQuery(
                original_query=query,
                rewritten_query=query,
            )
        
        yield {
            "type": "rag_info",
            "rewritten_query": rewrite_result.rewritten_query,
            "query_variations": rewrite_result.variations,
            "entities": rewrite_result.extracted_entities,
        }
        
        process_result = await self.process_query(query, kb_ids, top_k, history)
        
        if process_result.documents:
            yield {
                "type": "rag_sources",
                "sources": [
                    {
                        "kb_name": getattr(r, 'kb_name', ''),
                        "doc_name": getattr(r, 'doc_name', ''),
                        "score": r.score,
                    }
                    for r in process_result.documents[:5]
                ],
            }
        
        yield {
            "type": "rag_context",
            "formatted_context": process_result.formatted_context,
        }
    
    def add_message(self, role: str, content: str) -> None:
        """添加消息到上下文管理器"""
        context_manager = self._get_context_manager()
        context_manager.add_message(role, content)
    
    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        self.add_message("user", content)
    
    def add_assistant_message(self, content: str) -> None:
        """添加助手消息"""
        self.add_message("assistant", content)
    
    def as_tool(self) -> StructuredTool:
        """
        封装为工具供其他服务调用
        """
        
        async def run_rag_search(
            query: str,
            kb_ids: Optional[List[str]] = None,
            top_k: int = 5,
        ) -> str:
            result = await self.search(query, kb_ids, top_k)
            
            if not result.documents:
                return "未找到相关信息"
            
            return self._format_results(result.documents)
        
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
            kb_name = getattr(r, 'kb_name', '未知知识库')
            doc_name = getattr(r, 'doc_name', '未知文档')
            formatted.append(
                f"[{i}] 来源：{kb_name}/{doc_name}\n"
                f"    相关度：{r.score:.2f}\n"
                f"    内容：{r.content[:500]}{'...' if len(r.content) > 500 else ''}\n"
            )
        return "\n".join(formatted)

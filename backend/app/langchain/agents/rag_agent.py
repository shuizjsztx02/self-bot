from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import Optional, List

from app.langchain.llm import get_llm
from app.knowledge_base.schemas import SearchResult, RAGSearchInput


class RagAgent:
    """
    RAG知识库Agent
    
    职责：
    1. 知识库检索与RAG增强
    2. 提供检索工具供其他Agent调用
    3. 支持独立执行检索任务
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        user_id: Optional[str] = None,
        db_session=None,
    ):
        self._llm = llm
        self.user_id = user_id
        self.db_session = db_session
        
        self._search_service = None
        self._permission_service = None
        self._kb_service = None
    
    def _get_llm(self) -> ChatOpenAI:
        if self._llm is None:
            self._llm = get_llm()
        return self._llm
    
    async def _get_services(self):
        if self._search_service is None:
            from app.knowledge_base.services import SearchService, PermissionService, KnowledgeBaseService
            from app.knowledge_base.services.embedding import EmbeddingService
            from app.knowledge_base.vector_store import VectorStoreFactory
            from app.db.session import get_async_session
            
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
        独立执行知识库检索
        供Supervisor直接调用
        
        Args:
            query: 查询文本
            kb_ids: 知识库ID列表
            top_k: 返回结果数量
            use_rerank: 是否使用重排序
            use_hybrid: 是否使用混合检索（向量+BM25）
            hybrid_alpha: 向量检索权重（0-1），1-alpha为BM25权重
        """
        await self._get_services()
        
        accessible_kbs = await self._permission_service.get_accessible_kbs(self.user_id)
        
        if not accessible_kbs:
            return []
        
        if kb_ids:
            kb_ids = [kb for kb in kb_ids if kb in accessible_kbs]
        else:
            kb_ids = accessible_kbs
        
        if not kb_ids:
            return []
        
        if use_hybrid and hasattr(self._search_service, 'hybrid_search'):
            results = await self._hybrid_cross_search(
                kb_ids=kb_ids,
                query=query,
                top_k=top_k,
                alpha=hybrid_alpha,
                use_rerank=use_rerank,
            )
        else:
            results = await self._search_service.cross_search(
                kb_ids=kb_ids,
                query=query,
                top_k=top_k,
                use_rerank=use_rerank,
            )
        
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
        
        return results
    
    async def _hybrid_cross_search(
        self,
        kb_ids: List[str],
        query: str,
        top_k: int = 5,
        alpha: float = 0.5,
        use_rerank: bool = True,
    ) -> List[SearchResult]:
        """
        跨知识库混合检索
        
        对每个知识库执行混合检索，然后合并结果
        """
        import asyncio
        
        tasks = [
            self._search_service.hybrid_search(
                kb_id=kb_id,
                query=query,
                top_k=top_k * 2,
                alpha=alpha,
                use_rerank=False,
            )
            for kb_id in kb_ids
        ]
        
        results_per_kb = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_results = []
        seen_ids = set()
        
        for results in results_per_kb:
            if isinstance(results, Exception):
                continue
            for r in results:
                if r.chunk_id not in seen_ids:
                    seen_ids.add(r.chunk_id)
                    all_results.append(r)
        
        if not all_results:
            return []
        
        if use_rerank and self._search_service.reranker:
            all_results = await self._search_service._rerank(query, all_results)
        else:
            all_results.sort(key=lambda x: x.score, reverse=True)
        
        return all_results[:top_k]
    
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

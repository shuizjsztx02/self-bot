"""
多轮对话 RAG 管理器

整合所有 RAG 增强模块，提供统一的多轮对话检索接口

模块整合：
1. 查询重写 (query_rewriter) - 处理依赖上下文的查询
2. 上下文压缩 (compression) - 控制 Token 预算
3. 引用溯源 (attribution) - 追踪来源
4. 对话历史管理 - 管理多轮对话上下文
"""
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
import logging
import asyncio

from .query_rewriter import (
    QueryRewriter,
    QueryRewriteConfig,
    ConversationHistoryManager,
    ConversationTurn,
    RewrittenQuery,
)
from app.knowledge_base.services.compression import (
    ContextCompressor,
    CompressionConfig,
    CompressedDocument,
)
from app.knowledge_base.services.attribution import (
    SourceAttribution,
    RAGResponse,
    SourceReference,
)

logger = logging.getLogger(__name__)


@dataclass
class MultiTurnRAGConfig:
    """多轮对话 RAG 配置"""
    max_history_turns: int = 10
    max_context_tokens: int = 4000
    max_retrieved_docs: int = 10
    min_relevance_score: float = 0.3
    enable_query_rewrite: bool = True
    enable_compression: bool = True
    enable_attribution: bool = True
    enable_query_expansion: bool = True


@dataclass
class RetrievalResult:
    """检索结果"""
    query: str
    rewritten_query: Optional[str]
    query_variations: List[str]
    documents: List[Any]
    compressed_documents: List[CompressedDocument]
    formatted_context: str
    conversation_context: str
    entities: List[str]


class MultiTurnRAGManager:
    """
    多轮对话 RAG 管理器
    
    核心功能：
    1. 管理对话历史
    2. 查询重写与扩展
    3. 混合检索
    4. 上下文压缩
    5. 引用溯源
    """
    
    def __init__(
        self,
        config: Optional[MultiTurnRAGConfig] = None,
        token_counter: Optional[Any] = None,
        embedding_service: Optional[Any] = None,
        search_service: Optional[Any] = None,
        llm_client: Optional[Any] = None,
    ):
        self.config = config or MultiTurnRAGConfig()
        self.token_counter = token_counter
        self.embedding_service = embedding_service
        self.search_service = search_service
        self.llm_client = llm_client
        
        self.history_manager = ConversationHistoryManager(
            max_turns=self.config.max_history_turns,
            max_tokens=self.config.max_context_tokens // 2,
            token_counter=token_counter,
        )
        
        self.query_rewriter = QueryRewriter(
            config=QueryRewriteConfig(
                max_history_turns=self.config.max_history_turns,
                enable_query_expansion=self.config.enable_query_expansion,
            ),
            llm_client=llm_client,
        )
        
        self.context_compressor = ContextCompressor(
            config=CompressionConfig(
                max_tokens=self.config.max_context_tokens,
                min_relevance_score=self.config.min_relevance_score,
                max_documents=self.config.max_retrieved_docs,
            ),
            token_counter=token_counter,
            embedding_service=embedding_service,
        )
        
        self.source_attribution = SourceAttribution(
            embedding_service=embedding_service,
        )
    
    async def process_query(
        self,
        query: str,
        kb_ids: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> RetrievalResult:
        """
        处理查询
        
        完整流程：
        1. 查询重写
        2. 查询扩展
        3. 混合检索
        4. 上下文压缩
        5. 格式化输出
        
        Args:
            query: 用户查询
            kb_ids: 知识库 ID 列表
            top_k: 返回文档数量
        
        Returns:
            RetrievalResult 对象
        """
        history = self.history_manager.get_history()
        
        rewritten_query_result = await self._rewrite_query(query, history)
        
        all_queries = [rewritten_query_result.rewritten_query]
        if rewritten_query_result.variations:
            all_queries.extend(rewritten_query_result.variations)
        
        documents = await self._retrieve_documents(
            all_queries, kb_ids, top_k
        )
        
        conversation_context = self.history_manager.get_context_for_query(query)
        
        compressed_docs, formatted_context = await self._compress_context(
            rewritten_query_result.rewritten_query,
            documents,
            conversation_context,
        )
        
        return RetrievalResult(
            query=query,
            rewritten_query=rewritten_query_result.rewritten_query,
            query_variations=rewritten_query_result.variations,
            documents=documents,
            compressed_documents=compressed_docs,
            formatted_context=formatted_context,
            conversation_context=conversation_context,
            entities=rewritten_query_result.extracted_entities,
        )
    
    async def _rewrite_query(
        self,
        query: str,
        history: List[ConversationTurn],
    ) -> RewrittenQuery:
        """重写查询"""
        if not self.config.enable_query_rewrite:
            return RewrittenQuery(
                original_query=query,
                rewritten_query=query,
            )
        
        return await self.query_rewriter.rewrite(query, history)
    
    async def _retrieve_documents(
        self,
        queries: List[str],
        kb_ids: Optional[List[str]],
        top_k: int,
    ) -> List[Any]:
        """检索文档"""
        if not self.search_service:
            logger.warning("Search service not configured")
            return []
        
        all_docs = []
        seen_ids = set()
        
        for query in queries:
            try:
                if hasattr(self.search_service, 'hybrid_search') and kb_ids:
                    for kb_id in kb_ids:
                        docs = await self.search_service.hybrid_search(
                            kb_id=kb_id,
                            query=query,
                            top_k=top_k,
                        )
                        for doc in docs:
                            doc_id = getattr(doc, 'chunk_id', getattr(doc, 'id', str(id(doc))))
                            if doc_id not in seen_ids:
                                seen_ids.add(doc_id)
                                all_docs.append(doc)
                elif hasattr(self.search_service, 'search') and kb_ids:
                    for kb_id in kb_ids:
                        docs = await self.search_service.search(
                            kb_id=kb_id,
                            query=query,
                            top_k=top_k,
                        )
                        for doc in docs:
                            doc_id = getattr(doc, 'chunk_id', getattr(doc, 'id', str(id(doc))))
                            if doc_id not in seen_ids:
                                seen_ids.add(doc_id)
                                all_docs.append(doc)
            except Exception as e:
                logger.error(f"Retrieval failed for query '{query}': {e}")
        
        all_docs.sort(key=lambda x: getattr(x, 'score', 0), reverse=True)
        
        return all_docs[:self.config.max_retrieved_docs]
    
    async def _compress_context(
        self,
        query: str,
        documents: List[Any],
        conversation_context: str,
    ) -> tuple:
        """压缩上下文"""
        if not self.config.enable_compression:
            doc_contents = [getattr(d, 'content', '') for d in documents]
            formatted = "\n\n".join(doc_contents)
            return [], formatted
        
        formatted_context, compressed_docs = await self.context_compressor.compress_with_context(
            query=query,
            documents=documents,
            conversation_context=conversation_context,
            max_tokens=self.config.max_context_tokens,
        )
        
        return compressed_docs, formatted_context
    
    def add_user_message(self, content: str, intent: Optional[str] = None) -> None:
        """添加用户消息"""
        self.history_manager.add_message("user", content, intent)
    
    def add_assistant_message(self, content: str, intent: Optional[str] = None) -> None:
        """添加助手消息"""
        self.history_manager.add_message("assistant", content, intent)
    
    def create_rag_response(
        self,
        answer: str,
        retrieval_result: RetrievalResult,
    ) -> RAGResponse:
        """创建 RAG 响应"""
        if not self.config.enable_attribution:
            return RAGResponse(
                answer=answer,
                sources=[],
                segments=[],
                overall_confidence=1.0,
                query=retrieval_result.query,
                rewritten_query=retrieval_result.rewritten_query,
            )
        
        return self.source_attribution.create_response(
            answer=answer,
            source_documents=retrieval_result.documents,
            query=retrieval_result.query,
            rewritten_query=retrieval_result.rewritten_query,
        )
    
    def get_history(self, limit: Optional[int] = None) -> List[ConversationTurn]:
        """获取对话历史"""
        return self.history_manager.get_history(limit)
    
    def get_entities(self) -> List[str]:
        """获取缓存的实体"""
        return self.history_manager.get_entities()
    
    def clear_history(self) -> None:
        """清空对话历史"""
        self.history_manager.clear()
    
    async def chat_with_rag(
        self,
        query: str,
        kb_ids: Optional[List[str]] = None,
        top_k: int = 5,
        generate_response: Optional[Callable] = None,
    ) -> RAGResponse:
        """
        完整的 RAG 对话流程
        
        Args:
            query: 用户查询
            kb_ids: 知识库 ID 列表
            top_k: 检索文档数量
            generate_response: 生成回答的回调函数
        
        Returns:
            RAGResponse 对象
        """
        retrieval_result = await self.process_query(query, kb_ids, top_k)
        
        if generate_response:
            answer = await generate_response(
                query=retrieval_result.rewritten_query or query,
                context=retrieval_result.formatted_context,
            )
        else:
            answer = self._generate_default_response(retrieval_result)
        
        self.add_user_message(query)
        self.add_assistant_message(answer)
        
        return self.create_rag_response(answer, retrieval_result)
    
    def _generate_default_response(self, retrieval_result: RetrievalResult) -> str:
        """生成默认响应"""
        if not retrieval_result.documents:
            return "抱歉，我没有找到相关的信息。请尝试用不同的方式提问。"
        
        top_docs = retrieval_result.documents[:3]
        parts = []
        
        for i, doc in enumerate(top_docs, 1):
            content = getattr(doc, 'content', '')
            source = getattr(doc, 'doc_name', '未知来源')
            parts.append(f"{content[:200]}...")
        
        return "\n\n".join(parts)


class MultiTurnRAGPipeline:
    """
    多轮对话 RAG 管道
    
    提供更高级的封装，支持流式输出和回调
    """
    
    def __init__(
        self,
        manager: MultiTurnRAGManager,
        llm_client: Optional[Any] = None,
    ):
        self.manager = manager
        self.llm_client = llm_client
    
    async def chat(
        self,
        query: str,
        kb_ids: Optional[List[str]] = None,
        stream: bool = False,
    ) -> RAGResponse:
        """
        执行对话
        
        Args:
            query: 用户查询
            kb_ids: 知识库 ID 列表
            stream: 是否流式输出
        
        Returns:
            RAGResponse 对象
        """
        async def generate(query: str, context: str) -> str:
            if not self.llm_client:
                return self._simple_generate(query, context)
            
            prompt = self._build_prompt(query, context)
            
            try:
                if hasattr(self.llm_client, 'ainvoke'):
                    response = await self.llm_client.ainvoke(prompt)
                    if hasattr(response, 'content'):
                        return response.content
                    return str(response)
                else:
                    return self._simple_generate(query, context)
            except Exception as e:
                logger.error(f"LLM generation failed: {e}")
                return self._simple_generate(query, context)
        
        return await self.manager.chat_with_rag(
            query=query,
            kb_ids=kb_ids,
            generate_response=generate,
        )
    
    def _build_prompt(self, query: str, context: str) -> str:
        """构建提示词"""
        return f"""基于以下上下文信息回答用户问题。如果上下文中没有相关信息，请诚实地说不知道。

上下文：
{context}

用户问题：{query}

请提供准确、有帮助的回答："""
    
    def _simple_generate(self, query: str, context: str) -> str:
        """简单生成（无 LLM 时的 fallback）"""
        if not context:
            return "抱歉，我没有找到相关的信息。"
        
        return f"根据检索到的信息：\n\n{context[:500]}..."
    
    def reset(self) -> None:
        """重置管道状态"""
        self.manager.clear_history()

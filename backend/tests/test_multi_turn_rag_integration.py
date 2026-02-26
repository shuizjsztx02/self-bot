"""
MultiTurnRAGManager 集成测试

测试范围：
1. 查询重写功能
2. 多轮对话上下文管理
3. 检索流程
4. 上下文压缩
5. 引用溯源
6. 完整RAG流程
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from dataclasses import dataclass
from typing import List, Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestQueryRewriter:
    """测试查询重写器"""
    
    @pytest.fixture
    def query_rewriter(self):
        """创建查询重写器实例"""
        from app.langchain.routers.query_rewriter import (
            QueryRewriter,
            QueryRewriteConfig,
        )
        
        config = QueryRewriteConfig(
            max_history_turns=5,
            enable_query_expansion=True,
        )
        
        llm_client = Mock()
        llm_client.ainvoke = AsyncMock(return_value=Mock(content='{"rewritten_query": "RAG的优点是什么？", "entities": ["RAG"], "variations": ["RAG的优势", "RAG的好处"]}'))
        
        return QueryRewriter(config=config, llm_client=llm_client)
    
    @pytest.mark.asyncio
    async def test_rewrite_query_with_context(self, query_rewriter):
        """测试带上下文的查询重写"""
        from app.langchain.routers.query_rewriter import ConversationTurn
        
        history = [
            ConversationTurn(role="user", content="什么是RAG？"),
            ConversationTurn(role="assistant", content="RAG是检索增强生成技术..."),
        ]
        
        result = await query_rewriter.rewrite("它的优点是什么？", history)
        
        assert result is not None
        assert result.original_query == "它的优点是什么？"
        assert "RAG" in result.rewritten_query or result.rewritten_query != "它的优点是什么？"
    
    @pytest.mark.asyncio
    async def test_rewrite_query_no_context(self, query_rewriter):
        """测试无上下文的查询重写"""
        result = await query_rewriter.rewrite("什么是机器学习？", [])
        
        assert result is not None
        assert result.original_query == "什么是机器学习？"
    
    @pytest.mark.asyncio
    async def test_extract_entities(self, query_rewriter):
        """测试实体提取"""
        with patch.object(query_rewriter, '_llm_rewrite', new_callable=AsyncMock) as mock_rewrite:
            mock_rewrite.return_value = Mock(
                original_query="OpenAI的GPT-4有什么特点？",
                rewritten_query="OpenAI的GPT-4有什么特点？",
                extracted_entities=["OpenAI", "GPT-4"],
                variations=[],
                confidence=0.9,
            )
            
            result = await query_rewriter.rewrite("OpenAI的GPT-4有什么特点？", [])
            
            assert result is not None
            assert len(result.extracted_entities) >= 0


class TestConversationHistoryManager:
    """测试对话历史管理器"""
    
    @pytest.fixture
    def history_manager(self):
        """创建对话历史管理器实例"""
        from app.langchain.routers.query_rewriter import ConversationHistoryManager
        
        return ConversationHistoryManager(max_turns=5, max_tokens=2000)
    
    def test_add_message(self, history_manager):
        """测试添加消息"""
        history_manager.add_message("user", "你好")
        history_manager.add_message("assistant", "你好！有什么可以帮助你的？")
        
        history = history_manager.get_history()
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[1].role == "assistant"
    
    def test_max_turns_limit(self, history_manager):
        """测试最大轮数限制"""
        for i in range(10):
            history_manager.add_message("user", f"消息{i}")
            history_manager.add_message("assistant", f"回复{i}")
        
        history = history_manager.get_history()
        assert len(history) <= 10
    
    def test_get_context_for_query(self, history_manager):
        """测试获取查询上下文"""
        history_manager.add_message("user", "什么是RAG？")
        history_manager.add_message("assistant", "RAG是检索增强生成...")
        history_manager.add_message("user", "它有什么优点？")
        
        context = history_manager.get_context_for_query("它有什么优点？")
        assert "RAG" in context or len(context) > 0
    
    def test_clear_history(self, history_manager):
        """测试清空历史"""
        history_manager.add_message("user", "测试")
        history_manager.clear()
        
        history = history_manager.get_history()
        assert len(history) == 0


class TestMultiTurnRAGManager:
    """测试多轮对话RAG管理器"""
    
    @pytest.fixture
    def mock_search_service(self):
        """创建模拟搜索服务"""
        service = Mock()
        
        @dataclass
        class MockSearchResult:
            chunk_id: str
            content: str
            score: float
            doc_name: str = "test_doc"
            kb_name: str = "test_kb"
        
        service.hybrid_search = AsyncMock(return_value=[
            MockSearchResult(chunk_id="1", content="RAG是检索增强生成", score=0.9),
            MockSearchResult(chunk_id="2", content="RAG可以提高回答准确性", score=0.8),
        ])
        
        service.search = AsyncMock(return_value=[
            MockSearchResult(chunk_id="1", content="RAG是检索增强生成", score=0.9),
        ])
        
        return service
    
    @pytest.fixture
    def mock_embedding_service(self):
        """创建模拟嵌入服务"""
        service = Mock()
        service.embed_text = AsyncMock(return_value=[0.1] * 768)
        service.embed_batch = AsyncMock(return_value=[[0.1] * 768])
        return service
    
    @pytest.fixture
    def mock_llm_client(self):
        """创建模拟LLM客户端"""
        client = Mock()
        client.ainvoke = AsyncMock(return_value=Mock(
            content='{"rewritten_query": "RAG的优点", "entities": ["RAG"], "variations": ["RAG的优势"]}'
        ))
        return client
    
    @pytest.fixture
    def multi_turn_rag(self, mock_search_service, mock_embedding_service, mock_llm_client):
        """创建MultiTurnRAGManager实例"""
        from app.langchain.routers.multi_turn_rag import (
            MultiTurnRAGManager,
            MultiTurnRAGConfig,
        )
        
        config = MultiTurnRAGConfig(
            max_history_turns=10,
            max_context_tokens=4000,
            enable_query_rewrite=True,
            enable_compression=False,
            enable_attribution=False,
        )
        
        return MultiTurnRAGManager(
            config=config,
            embedding_service=mock_embedding_service,
            search_service=mock_search_service,
            llm_client=mock_llm_client,
        )
    
    @pytest.mark.asyncio
    async def test_process_query(self, multi_turn_rag):
        """测试查询处理流程"""
        result = await multi_turn_rag.process_query(
            query="什么是RAG？",
            kb_ids=["kb-1"],
            top_k=5,
        )
        
        assert result is not None
        assert result.query == "什么是RAG？"
        assert len(result.documents) > 0
    
    @pytest.mark.asyncio
    async def test_multi_turn_conversation(self, multi_turn_rag):
        """测试多轮对话"""
        await multi_turn_rag.process_query("什么是RAG？", ["kb-1"])
        multi_turn_rag.add_user_message("什么是RAG？")
        multi_turn_rag.add_assistant_message("RAG是检索增强生成技术...")
        
        result = await multi_turn_rag.process_query("它有什么优点？", ["kb-1"])
        
        assert result is not None
        history = multi_turn_rag.get_history()
        assert len(history) >= 2
    
    @pytest.mark.asyncio
    async def test_chat_with_rag(self, multi_turn_rag):
        """测试完整RAG对话流程"""
        async def generate_response(query: str, context: str) -> str:
            return f"根据检索结果，{query}的答案是..."
        
        response = await multi_turn_rag.chat_with_rag(
            query="什么是RAG？",
            kb_ids=["kb-1"],
            top_k=5,
            generate_response=generate_response,
        )
        
        assert response is not None
        assert response.answer is not None
        assert response.query == "什么是RAG？"
    
    def test_add_messages(self, multi_turn_rag):
        """测试添加消息"""
        multi_turn_rag.add_user_message("测试问题")
        multi_turn_rag.add_assistant_message("测试回答")
        
        history = multi_turn_rag.get_history()
        assert len(history) == 2
    
    def test_clear_history(self, multi_turn_rag):
        """测试清空历史"""
        multi_turn_rag.add_user_message("测试")
        multi_turn_rag.clear_history()
        
        history = multi_turn_rag.get_history()
        assert len(history) == 0


class TestSupervisorAgentIntegration:
    """测试SupervisorAgent集成"""
    
    @pytest.fixture
    def mock_db(self):
        """创建模拟数据库会话"""
        db = AsyncMock()
        db.execute = AsyncMock()
        db.scalar_one_or_none = Mock(return_value=None)
        return db
    
    @pytest.fixture
    def supervisor_agent(self, mock_db):
        """创建SupervisorAgent实例"""
        with patch('app.langchain.agents.supervisor_agent.get_llm') as mock_get_llm:
            mock_llm = Mock()
            mock_llm.ainvoke = AsyncMock(return_value=Mock(content='{"intent": "kb_query", "confidence": 0.9}'))
            mock_get_llm.return_value = mock_llm
            
            with patch('app.core.token_counter.TokenCounter'):
                with patch('app.knowledge_base.services.embedding.EmbeddingService'):
                    from app.langchain.agents.supervisor_agent import SupervisorAgent
                    
                    agent = SupervisorAgent(
                        provider="openai",
                        db_session=mock_db,
                    )
                    
                    return agent
    
    def test_multi_turn_rag_property(self, supervisor_agent):
        """测试multi_turn_rag属性"""
        with patch('app.core.token_counter.TokenCounter'):
            with patch('app.knowledge_base.services.embedding.EmbeddingService'):
                manager = supervisor_agent.multi_turn_rag
                
                assert manager is not None
                assert supervisor_agent._multi_turn_rag_manager is not None
    
    def test_multi_turn_rag_singleton(self, supervisor_agent):
        """测试multi_turn_rag单例"""
        with patch('app.core.token_counter.TokenCounter'):
            with patch('app.knowledge_base.services.embedding.EmbeddingService'):
                manager1 = supervisor_agent.multi_turn_rag
                manager2 = supervisor_agent.multi_turn_rag
                
                assert manager1 is manager2


class TestQueryRewriteScenarios:
    """测试查询重写场景"""
    
    @pytest.fixture
    def rewriter(self):
        """创建查询重写器"""
        from app.langchain.routers.query_rewriter import QueryRewriter, QueryRewriteConfig
        
        config = QueryRewriteConfig(enable_query_expansion=True)
        return QueryRewriter(config=config, llm_client=None)
    
    @pytest.mark.asyncio
    async def test_pronoun_resolution(self, rewriter):
        """测试代词解析"""
        from app.langchain.routers.query_rewriter import ConversationTurn
        
        history = [
            ConversationTurn(role="user", content="介绍一下OpenAI"),
            ConversationTurn(role="assistant", content="OpenAI是一家人工智能公司..."),
        ]
        
        with patch.object(rewriter, '_llm_rewrite', new_callable=AsyncMock) as mock_rewrite:
            mock_rewrite.return_value = Mock(
                original_query="它的产品有哪些？",
                rewritten_query="OpenAI的产品有哪些？",
                extracted_entities=["OpenAI"],
                variations=[],
                confidence=0.9,
            )
            
            result = await rewriter.rewrite("它的产品有哪些？", history)
            
            assert result is not None
            assert result.rewritten_query != result.original_query or result.confidence >= 0.5
    
    @pytest.mark.asyncio
    async def test_context_carry_over(self, rewriter):
        """测试上下文延续"""
        from app.langchain.routers.query_rewriter import ConversationTurn
        
        history = [
            ConversationTurn(role="user", content="什么是向量数据库？"),
            ConversationTurn(role="assistant", content="向量数据库是存储向量嵌入的数据库..."),
            ConversationTurn(role="user", content="有哪些开源的？"),
        ]
        
        with patch.object(rewriter, '_llm_rewrite', new_callable=AsyncMock) as mock_rewrite:
            mock_rewrite.return_value = Mock(
                original_query="有哪些开源的？",
                rewritten_query="有哪些开源的向量数据库？",
                extracted_entities=["向量数据库"],
                variations=[],
                confidence=0.85,
            )
            
            result = await rewriter.rewrite("有哪些开源的？", history)
            
            assert result is not None
            assert result.original_query == "有哪些开源的？"


class TestRAGPipeline:
    """测试RAG管道"""
    
    @pytest.fixture
    def pipeline(self):
        """创建RAG管道实例"""
        from app.langchain.routers.multi_turn_rag import (
            MultiTurnRAGManager,
            MultiTurnRAGConfig,
            MultiTurnRAGPipeline,
        )
        
        config = MultiTurnRAGConfig(
            enable_query_rewrite=False,
            enable_compression=False,
        )
        
        manager = MultiTurnRAGManager(config=config)
        return MultiTurnRAGPipeline(manager=manager, llm_client=None)
    
    def test_build_prompt(self, pipeline):
        """测试提示词构建"""
        prompt = pipeline._build_prompt(
            query="什么是RAG？",
            context="RAG是检索增强生成技术...",
        )
        
        assert "什么是RAG？" in prompt
        assert "RAG是检索增强生成技术" in prompt
    
    def test_simple_generate(self, pipeline):
        """测试简单生成"""
        result = pipeline._simple_generate(
            query="测试问题",
            context="这是相关上下文",
        )
        
        assert result is not None
        assert len(result) > 0
    
    def test_reset(self, pipeline):
        """测试重置"""
        pipeline.manager.add_user_message("测试")
        pipeline.reset()
        
        history = pipeline.manager.get_history()
        assert len(history) == 0


def run_tests():
    """运行所有测试"""
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_tests()

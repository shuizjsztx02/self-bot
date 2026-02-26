"""
阶段二优化功能测试

测试内容：
1. QueryRewriter - 查询重写
2. EntityExtractor - 实体提取
3. PronounResolver - 代词解析
4. ContextCompressor - 上下文压缩
5. SourceAttribution - 引用溯源
6. MultiTurnRAGManager - 多轮对话管理
"""
import pytest
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestEntityExtractor:
    """实体提取器测试"""
    
    def test_extract_chinese_entities(self):
        """测试中文实体提取"""
        from app.langchain.routers.query_rewriter import EntityExtractor
        
        extractor = EntityExtractor()
        text = "苹果公司发布了新产品iPhone，微软公司也跟进推出了Surface电脑"
        
        entities = extractor.extract(text)
        
        assert len(entities) > 0
        assert any("苹果" in e or "公司" in e for e in entities)
    
    def test_extract_from_history(self):
        """测试从对话历史提取实体"""
        from app.langchain.routers.query_rewriter import EntityExtractor, ConversationTurn
        
        extractor = EntityExtractor()
        history = [
            ConversationTurn(role="user", content="苹果公司最近有什么新闻？"),
            ConversationTurn(role="assistant", content="苹果公司发布了新iPhone"),
            ConversationTurn(role="user", content="微软呢？"),
        ]
        
        entities = extractor.extract_from_history(history)
        
        assert len(entities) > 0


class TestPronounResolver:
    """代词解析器测试"""
    
    def test_detect_chinese_pronouns(self):
        """测试中文代词检测"""
        from app.langchain.routers.query_rewriter import PronounResolver
        
        resolver = PronounResolver()
        
        pronouns = resolver.detect_pronouns("它的股价是多少？")
        assert len(pronouns) > 0
        assert pronouns[0][0] == "它"
        
        pronouns = resolver.detect_pronouns("这个产品的价格")
        assert len(pronouns) > 0
    
    def test_resolve_pronouns(self):
        """测试代词解析"""
        from app.langchain.routers.query_rewriter import (
            PronounResolver, EntityExtractor, ConversationTurn
        )
        
        resolver = PronounResolver()
        extractor = EntityExtractor()
        
        history = [
            ConversationTurn(role="user", content="苹果公司最近有什么新闻？"),
            ConversationTurn(role="assistant", content="苹果公司发布了新iPhone"),
        ]
        
        entities = extractor.extract_from_history(history)
        
        rewritten, confidence = resolver.resolve(
            "它的股价是多少？",
            entities,
            history,
        )
        
        assert "它" not in rewritten or confidence < 1.0
    
    def test_no_pronouns(self):
        """测试无代词情况"""
        from app.langchain.routers.query_rewriter import PronounResolver
        
        resolver = PronounResolver()
        
        rewritten, confidence = resolver.resolve(
            "苹果公司的股价是多少？",
            [],
            [],
        )
        
        assert rewritten == "苹果公司的股价是多少？"
        assert confidence == 1.0


class TestQueryExpander:
    """查询扩展器测试"""
    
    def test_expand_with_synonyms(self):
        """测试同义词扩展"""
        from app.langchain.routers.query_rewriter import QueryExpander
        
        expander = QueryExpander()
        
        variations = expander.expand("苹果公司的股票价格是多少？")
        
        assert isinstance(variations, list)
    
    def test_no_expansion_possible(self):
        """测试无法扩展的情况"""
        from app.langchain.routers.query_rewriter import QueryExpander
        
        expander = QueryExpander()
        
        variations = expander.expand("今天天气怎么样？")
        
        assert isinstance(variations, list)


class TestQueryRewriter:
    """查询重写器测试"""
    
    def test_rewrite_simple_query(self):
        """测试简单查询重写"""
        from app.langchain.routers.query_rewriter import QueryRewriter
        
        rewriter = QueryRewriter()
        
        result = asyncio.run(rewriter.rewrite("苹果公司是什么？"))
        
        assert result.original_query == "苹果公司是什么？"
        assert result.rewritten_query is not None
    
    def test_rewrite_with_history(self):
        """测试带历史的查询重写"""
        from app.langchain.routers.query_rewriter import (
            QueryRewriter, ConversationTurn
        )
        
        rewriter = QueryRewriter()
        history = [
            ConversationTurn(role="user", content="苹果公司最近有什么新闻？"),
            ConversationTurn(role="assistant", content="苹果发布了新iPhone"),
        ]
        
        result = asyncio.run(rewriter.rewrite("它的股价呢？", history))
        
        assert result.original_query == "它的股价呢？"
        assert len(result.extracted_entities) > 0 or result.confidence < 1.0
    
    def test_create_turn(self):
        """测试创建对话轮次"""
        from app.langchain.routers.query_rewriter import QueryRewriter
        
        rewriter = QueryRewriter()
        
        turn = rewriter.create_turn("user", "苹果公司发布了新产品")
        
        assert turn.role == "user"
        assert turn.content == "苹果公司发布了新产品"
        assert isinstance(turn.entities, list)


class TestConversationHistoryManager:
    """对话历史管理器测试"""
    
    def test_add_messages(self):
        """测试添加消息"""
        from app.langchain.routers.query_rewriter import ConversationHistoryManager
        
        manager = ConversationHistoryManager()
        
        manager.add_message("user", "你好")
        manager.add_message("assistant", "你好！有什么可以帮助你的？")
        
        history = manager.get_history()
        
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[1].role == "assistant"
    
    def test_max_turns_limit(self):
        """测试最大轮次限制"""
        from app.langchain.routers.query_rewriter import ConversationHistoryManager
        
        manager = ConversationHistoryManager(max_turns=3)
        
        for i in range(5):
            manager.add_message("user", f"消息{i}")
        
        history = manager.get_history()
        
        assert len(history) <= 3
    
    def test_get_context_for_query(self):
        """测试获取查询上下文"""
        from app.langchain.routers.query_rewriter import ConversationHistoryManager
        
        manager = ConversationHistoryManager()
        
        manager.add_message("user", "苹果公司是什么？")
        manager.add_message("assistant", "苹果公司是一家科技公司")
        
        context = manager.get_context_for_query("它的产品有哪些？")
        
        assert "苹果公司" in context
        assert "科技公司" in context
    
    def test_get_entities(self):
        """测试获取实体"""
        from app.langchain.routers.query_rewriter import ConversationHistoryManager
        
        manager = ConversationHistoryManager()
        
        manager.add_message("user", "苹果公司和微软公司有什么区别？")
        
        entities = manager.get_entities()
        
        assert isinstance(entities, list)


class TestContextCompressor:
    """上下文压缩器测试"""
    
    def test_sentence_splitter(self):
        """测试句子分割"""
        from app.knowledge_base.services.compression import SentenceSplitter
        
        splitter = SentenceSplitter()
        
        text = "这是第一句。这是第二句！这是第三句？"
        sentences = splitter.split(text)
        
        assert len(sentences) == 3
    
    def test_sentence_splitter_chinese(self):
        """测试中文句子分割"""
        from app.knowledge_base.services.compression import SentenceSplitter
        
        splitter = SentenceSplitter()
        
        text = "苹果公司是一家科技公司。总部位于加州。"
        sentences = splitter.split(text)
        
        assert len(sentences) == 2
    
    @pytest.mark.asyncio
    async def test_compress_documents(self):
        """测试文档压缩"""
        from app.knowledge_base.services.compression import (
            ContextCompressor, CompressionConfig
        )
        from dataclasses import dataclass
        
        @dataclass
        class MockDoc:
            id: str
            content: str
            score: float
        
        compressor = ContextCompressor(config=CompressionConfig(max_tokens=500))
        
        documents = [
            MockDoc(id="1", content="苹果公司是一家科技公司，总部位于加州库比蒂诺。", score=0.9),
            MockDoc(id="2", content="微软公司是一家软件公司，总部位于华盛顿州。", score=0.8),
        ]
        
        compressed = await compressor.compress("苹果公司", documents)
        
        assert isinstance(compressed, list)
    
    @pytest.mark.asyncio
    async def test_compress_empty_documents(self):
        """测试空文档列表"""
        from app.knowledge_base.services.compression import ContextCompressor
        
        compressor = ContextCompressor()
        
        compressed = await compressor.compress("测试查询", [])
        
        assert compressed == []


class TestSourceAttribution:
    """引用溯源测试"""
    
    def test_source_reference_citation(self):
        """测试来源引用格式化"""
        from app.knowledge_base.services.attribution import SourceReference
        
        source = SourceReference(
            doc_id="doc1",
            chunk_id="chunk1",
            content="测试内容",
            score=0.9,
            doc_name="测试文档",
            page_number=10,
        )
        
        citation = source.to_citation("standard")
        assert "测试文档" in citation
        
        citation = source.to_citation("academic")
        assert "[测试文档]" == citation
    
    def test_source_tracker(self):
        """测试来源追踪"""
        from app.knowledge_base.services.attribution import SourceTracker
        from dataclasses import dataclass
        
        @dataclass
        class MockDoc:
            doc_id: str
            id: str
            content: str
            score: float
        
        tracker = SourceTracker()
        
        answer = "苹果公司是一家科技公司。总部位于加州。"
        documents = [
            MockDoc(doc_id="1", id="c1", content="苹果公司是一家科技公司", score=0.9),
            MockDoc(doc_id="2", id="c2", content="总部位于加州库比蒂诺", score=0.8),
        ]
        
        segments = tracker.track_sources(answer, documents)
        
        assert isinstance(segments, list)
    
    def test_confidence_evaluator(self):
        """测试置信度评估"""
        from app.knowledge_base.services.attribution import (
            ConfidenceEvaluator, SourceReference
        )
        
        evaluator = ConfidenceEvaluator()
        
        sources = [
            SourceReference(doc_id="1", chunk_id="c1", content="内容1", score=0.9),
            SourceReference(doc_id="2", chunk_id="c2", content="内容2", score=0.8),
        ]
        
        confidence = evaluator.evaluate("测试回答", sources, [])
        
        assert 0 <= confidence <= 1
    
    def test_rag_response(self):
        """测试 RAG 响应"""
        from app.knowledge_base.services.attribution import (
            RAGResponse, SourceReference
        )
        
        response = RAGResponse(
            answer="这是回答",
            sources=[
                SourceReference(doc_id="1", chunk_id="c1", content="来源1", score=0.9)
            ],
            segments=[],
            overall_confidence=0.85,
            query="测试问题",
        )
        
        formatted = response.get_formatted_answer(include_citations=True)
        
        assert "这是回答" in formatted
        assert "参考来源" in formatted
        
        result_dict = response.to_dict()
        
        assert result_dict["answer"] == "这是回答"
        assert len(result_dict["sources"]) == 1


class TestCitationGenerator:
    """引用生成器测试"""
    
    def test_generate_bibliography(self):
        """测试生成参考文献"""
        from app.knowledge_base.services.attribution import (
            CitationGenerator, SourceReference
        )
        
        sources = [
            SourceReference(doc_id="1", chunk_id="c1", content="内容", score=0.9, doc_name="文档A"),
            SourceReference(doc_id="2", chunk_id="c2", content="内容", score=0.8, doc_name="文档B"),
        ]
        
        bibliography = CitationGenerator.generate_bibliography(sources)
        
        assert "参考文献" in bibliography
        assert "文档A" in bibliography
    
    def test_generate_bibliography_empty(self):
        """测试空来源"""
        from app.knowledge_base.services.attribution import CitationGenerator
        
        bibliography = CitationGenerator.generate_bibliography([])
        
        assert bibliography == ""


class TestMultiTurnRAGConfig:
    """多轮对话 RAG 配置测试"""
    
    def test_default_config(self):
        """测试默认配置"""
        from app.langchain.routers.multi_turn_rag import MultiTurnRAGConfig
        
        config = MultiTurnRAGConfig()
        
        assert config.max_history_turns == 10
        assert config.max_context_tokens == 4000
        assert config.enable_query_rewrite == True
        assert config.enable_compression == True
        assert config.enable_attribution == True


class TestMultiTurnRAGManager:
    """多轮对话 RAG 管理器测试"""
    
    def test_manager_initialization(self):
        """测试管理器初始化"""
        from app.langchain.routers.multi_turn_rag import MultiTurnRAGManager
        
        manager = MultiTurnRAGManager()
        
        assert manager.history_manager is not None
        assert manager.query_rewriter is not None
        assert manager.context_compressor is not None
        assert manager.source_attribution is not None
    
    def test_add_messages(self):
        """测试添加消息"""
        from app.langchain.routers.multi_turn_rag import MultiTurnRAGManager
        
        manager = MultiTurnRAGManager()
        
        manager.add_user_message("你好")
        manager.add_assistant_message("你好！有什么可以帮助你的？")
        
        history = manager.get_history()
        
        assert len(history) == 2
    
    def test_clear_history(self):
        """测试清空历史"""
        from app.langchain.routers.multi_turn_rag import MultiTurnRAGManager
        
        manager = MultiTurnRAGManager()
        
        manager.add_user_message("测试消息")
        manager.clear_history()
        
        history = manager.get_history()
        
        assert len(history) == 0
    
    def test_get_entities(self):
        """测试获取实体"""
        from app.langchain.routers.multi_turn_rag import MultiTurnRAGManager
        
        manager = MultiTurnRAGManager()
        
        manager.add_user_message("苹果公司和微软公司有什么区别？")
        
        entities = manager.get_entities()
        
        assert isinstance(entities, list)


class TestRetrievalResult:
    """检索结果测试"""
    
    def test_retrieval_result_creation(self):
        """测试检索结果创建"""
        from app.langchain.routers.multi_turn_rag import RetrievalResult
        
        result = RetrievalResult(
            query="测试查询",
            rewritten_query="重写后的查询",
            query_variations=["变体1", "变体2"],
            documents=[],
            compressed_documents=[],
            formatted_context="格式化上下文",
            conversation_context="对话上下文",
            entities=["实体1"],
        )
        
        assert result.query == "测试查询"
        assert result.rewritten_query == "重写后的查询"
        assert len(result.query_variations) == 2


def run_tests():
    """运行所有测试"""
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_tests()

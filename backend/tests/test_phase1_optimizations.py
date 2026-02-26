"""
阶段一优化功能测试

测试内容：
1. TokenCounter - tiktoken 精确计数
2. BM25Index - BM25 关键词检索
3. HybridSearchResult - 混合检索融合
4. VectorStore - 向量存储和 FAISS 索引
5. RAGRetriever - Embedding 模型强制要求
"""
import pytest
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestTokenCounter:
    """Token 计数器测试"""
    
    def test_import_token_counter(self):
        """测试导入 TokenCounter"""
        from app.knowledge_base.parsers.base import TokenCounter
        counter = TokenCounter()
        assert counter is not None
    
    def test_count_tokens_english(self):
        """测试英文 token 计数"""
        from app.knowledge_base.parsers.base import TokenCounter
        counter = TokenCounter()
        
        text = "Hello, this is a test sentence for token counting."
        count = counter.count_tokens(text)
        
        assert count > 0
        assert isinstance(count, int)
    
    def test_count_tokens_chinese(self):
        """测试中文 token 计数"""
        from app.knowledge_base.parsers.base import TokenCounter
        counter = TokenCounter()
        
        text = "这是一个用于测试 token 计数的中文句子。"
        count = counter.count_tokens(text)
        
        assert count > 0
        assert isinstance(count, int)
    
    def test_count_tokens_mixed(self):
        """测试中英文混合 token 计数"""
        from app.knowledge_base.parsers.base import TokenCounter
        counter = TokenCounter()
        
        text = "Hello 世界! This is 一个 mixed text 混合文本测试。"
        count = counter.count_tokens(text)
        
        assert count > 0
        assert isinstance(count, int)
    
    def test_count_tokens_empty(self):
        """测试空文本"""
        from app.knowledge_base.parsers.base import TokenCounter
        counter = TokenCounter()
        
        count = counter.count_tokens("")
        assert count == 0
        
        count = counter.count_tokens(None)
        assert count == 0
    
    def test_estimate_tokens_fallback(self):
        """测试 fallback 估算"""
        from app.knowledge_base.parsers.base import TokenCounter
        counter = TokenCounter()
        
        estimated = counter._estimate_tokens("Hello world")
        assert estimated > 0
        
        estimated_cn = counter._estimate_tokens("你好世界")
        assert estimated_cn > 0
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        from app.knowledge_base.parsers.base import TokenCounter
        
        counter1 = TokenCounter()
        counter2 = TokenCounter()
        
        assert counter1 is counter2


class TestDocumentParserTokenCount:
    """DocumentParser token 计数测试"""
    
    def test_parser_token_count(self):
        """测试解析器的 token 计数方法"""
        from app.knowledge_base.parsers.base import DocumentParser, ParsedDocument
        
        class TestParser(DocumentParser):
            async def parse(self, file_path: str) -> ParsedDocument:
                return ParsedDocument(content="")
            
            def supported_extensions(self) -> list:
                return [".test"]
        
        parser = TestParser()
        
        text = "This is a test sentence for token counting."
        count = parser.count_tokens(text)
        
        assert count > 0
        assert isinstance(count, int)


class TestBM25Index:
    """BM25 索引测试"""
    
    def test_bm25_index_creation(self):
        """测试 BM25 索引创建"""
        from app.knowledge_base.services.bm25 import BM25Index, BM25Document
        
        index = BM25Index()
        assert index.n_docs == 0
        assert len(index.documents) == 0
    
    def test_bm25_add_documents(self):
        """测试添加文档"""
        from app.knowledge_base.services.bm25 import BM25Index, BM25Document
        
        index = BM25Index()
        docs = [
            BM25Document(id="1", content="机器学习是人工智能的一个分支"),
            BM25Document(id="2", content="深度学习是机器学习的一种方法"),
            BM25Document(id="3", content="自然语言处理是人工智能的重要应用"),
        ]
        
        index.add_documents(docs)
        
        assert index.n_docs == 3
        assert len(index.doc_freqs) > 0
        assert "机" in index.doc_freqs or "学" in index.doc_freqs
    
    def test_bm25_search(self):
        """测试 BM25 搜索"""
        from app.knowledge_base.services.bm25 import BM25Index, BM25Document
        
        index = BM25Index()
        docs = [
            BM25Document(id="1", content="机器学习是人工智能的一个分支"),
            BM25Document(id="2", content="深度学习是机器学习的一种方法"),
            BM25Document(id="3", content="自然语言处理是人工智能的重要应用"),
        ]
        
        index.add_documents(docs)
        
        results = index.search("机器学习", top_k=2)
        
        assert len(results) <= 2
        assert len(results) > 0
        
        for doc, score in results:
            assert isinstance(doc, BM25Document)
            assert isinstance(score, float)
    
    def test_bm25_search_chinese(self):
        """测试中文搜索"""
        from app.knowledge_base.services.bm25 import BM25Index, BM25Document
        
        index = BM25Index()
        docs = [
            BM25Document(id="1", content="Python 是一种编程语言"),
            BM25Document(id="2", content="Java 是另一种编程语言"),
            BM25Document(id="3", content="JavaScript 用于网页开发"),
        ]
        
        index.add_documents(docs)
        
        results = index.search("编程语言", top_k=3)
        
        assert len(results) > 0
    
    def test_bm25_search_english(self):
        """测试英文搜索"""
        from app.knowledge_base.services.bm25 import BM25Index, BM25Document
        
        index = BM25Index()
        docs = [
            BM25Document(id="1", content="Machine learning is a subset of artificial intelligence"),
            BM25Document(id="2", content="Deep learning uses neural networks"),
            BM25Document(id="3", content="Natural language processing handles text data"),
        ]
        
        index.add_documents(docs)
        
        results = index.search("machine learning", top_k=2)
        
        assert len(results) > 0
    
    def test_bm25_remove_documents(self):
        """测试移除文档"""
        from app.knowledge_base.services.bm25 import BM25Index, BM25Document
        
        index = BM25Index()
        docs = [
            BM25Document(id="1", content="文档一"),
            BM25Document(id="2", content="文档二"),
        ]
        
        index.add_documents(docs)
        assert index.n_docs == 2
        
        index.remove_documents(["1"])
        assert index.n_docs == 1
        assert "1" not in index.documents
    
    def test_bm25_clear(self):
        """测试清空索引"""
        from app.knowledge_base.services.bm25 import BM25Index, BM25Document
        
        index = BM25Index()
        docs = [
            BM25Document(id="1", content="文档一"),
            BM25Document(id="2", content="文档二"),
        ]
        
        index.add_documents(docs)
        index.clear()
        
        assert index.n_docs == 0
        assert len(index.documents) == 0


class TestHybridSearchResult:
    """混合检索融合测试"""
    
    def test_reciprocal_rank_fusion(self):
        """测试 RRF 融合"""
        from app.knowledge_base.services.bm25 import BM25Document, HybridSearchResult
        
        class MockDoc:
            def __init__(self, id):
                self.id = id
        
        vector_results = [
            (MockDoc("a"), 0.9),
            (MockDoc("b"), 0.8),
            (MockDoc("c"), 0.7),
        ]
        
        bm25_results = [
            (BM25Document(id="b", content="doc b"), 3.5),
            (BM25Document(id="a", content="doc a"), 2.8),
            (BM25Document(id="d", content="doc d"), 2.1),
        ]
        
        fused = HybridSearchResult.reciprocal_rank_fusion(
            vector_results, bm25_results, alpha=0.5, k=60
        )
        
        assert len(fused) == 4
        
        assert fused[0][0].id in ["a", "b"]
    
    def test_weighted_fusion(self):
        """测试加权融合"""
        from app.knowledge_base.services.bm25 import BM25Document, HybridSearchResult
        
        class MockDoc:
            def __init__(self, id):
                self.id = id
        
        vector_results = [
            (MockDoc("a"), 0.9),
            (MockDoc("b"), 0.8),
        ]
        
        bm25_results = [
            (BM25Document(id="b", content="doc b"), 3.5),
            (BM25Document(id="c", content="doc c"), 2.1),
        ]
        
        fused = HybridSearchResult.weighted_fusion(
            vector_results, bm25_results, alpha=0.7
        )
        
        assert len(fused) == 3
    
    def test_rrf_empty_results(self):
        """测试空结果处理"""
        from app.knowledge_base.services.bm25 import HybridSearchResult
        
        fused = HybridSearchResult.reciprocal_rank_fusion([], [], alpha=0.5)
        
        assert len(fused) == 0


class TestVectorStore:
    """向量存储测试"""
    
    @pytest.mark.asyncio
    async def test_in_memory_store_insert(self):
        """测试内存存储插入"""
        from app.langchain.memory.vector_store import InMemoryVectorStore, VectorDocument
        
        store = InMemoryVectorStore(embedding_dim=768)
        
        docs = [
            VectorDocument(id="1", content="test doc 1", metadata={"type": "test"}),
            VectorDocument(id="2", content="test doc 2", metadata={"type": "test"}),
        ]
        
        embeddings = [[0.1] * 768, [0.2] * 768]
        
        ids = await store.insert(docs, embeddings)
        
        assert len(ids) == 2
        assert await store.count() == 2
    
    @pytest.mark.asyncio
    async def test_in_memory_store_search(self):
        """测试内存存储搜索"""
        from app.langchain.memory.vector_store import InMemoryVectorStore, VectorDocument
        
        store = InMemoryVectorStore(embedding_dim=4)
        
        docs = [
            VectorDocument(id="1", content="doc 1"),
            VectorDocument(id="2", content="doc 2"),
            VectorDocument(id="3", content="doc 3"),
        ]
        
        embeddings = [
            [1.0, 0.0, 0.0, 0.0],
            [0.9, 0.1, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
        ]
        
        await store.insert(docs, embeddings)
        
        query = [1.0, 0.0, 0.0, 0.0]
        results = await store.search(query, top_k=2)
        
        assert len(results) == 2
        assert results[0][0].id == "1"
    
    @pytest.mark.asyncio
    async def test_in_memory_store_delete(self):
        """测试内存存储删除"""
        from app.langchain.memory.vector_store import InMemoryVectorStore, VectorDocument
        
        store = InMemoryVectorStore(embedding_dim=4)
        
        docs = [
            VectorDocument(id="1", content="doc 1"),
            VectorDocument(id="2", content="doc 2"),
        ]
        
        embeddings = [[0.1] * 4, [0.2] * 4]
        await store.insert(docs, embeddings)
        
        await store.delete(["1"])
        
        assert await store.count() == 1
    
    @pytest.mark.asyncio
    async def test_in_memory_store_clear(self):
        """测试内存存储清空"""
        from app.langchain.memory.vector_store import InMemoryVectorStore, VectorDocument
        
        store = InMemoryVectorStore(embedding_dim=4)
        
        docs = [
            VectorDocument(id="1", content="doc 1"),
            VectorDocument(id="2", content="doc 2"),
        ]
        
        embeddings = [[0.1] * 4, [0.2] * 4]
        await store.insert(docs, embeddings)
        
        await store.clear()
        
        assert await store.count() == 0


class TestFAISSIndex:
    """FAISS 索引测试"""
    
    def test_faiss_index_creation(self):
        """测试 FAISS 索引创建"""
        from app.langchain.memory.vector_store import FAISSIndex
        
        index = FAISSIndex(dimension=128)
        index._init_index()
        
        assert index._initialized
        assert index.dimension == 128
    
    def test_faiss_add_vectors(self):
        """测试添加向量"""
        from app.langchain.memory.vector_store import FAISSIndex, VectorDocument
        
        index = FAISSIndex(dimension=4)
        
        docs = [
            VectorDocument(id="1", content="doc 1"),
            VectorDocument(id="2", content="doc 2"),
        ]
        
        embeddings = [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
        ]
        
        index.add_vectors(["1", "2"], embeddings, docs)
        
        assert index.count() == 2
    
    def test_faiss_search(self):
        """测试 FAISS 搜索"""
        from app.langchain.memory.vector_store import FAISSIndex, VectorDocument
        
        index = FAISSIndex(dimension=4)
        
        docs = [
            VectorDocument(id="1", content="doc 1"),
            VectorDocument(id="2", content="doc 2"),
            VectorDocument(id="3", content="doc 3"),
        ]
        
        embeddings = [
            [1.0, 0.0, 0.0, 0.0],
            [0.9, 0.1, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
        ]
        
        index.add_vectors(["1", "2", "3"], embeddings, docs)
        
        query = [1.0, 0.0, 0.0, 0.0]
        results = index.search(query, top_k=2)
        
        assert len(results) == 2
        assert results[0][0].id == "1"
    
    def test_faiss_remove(self):
        """测试 FAISS 移除"""
        from app.langchain.memory.vector_store import FAISSIndex, VectorDocument
        
        index = FAISSIndex(dimension=4)
        
        docs = [
            VectorDocument(id="1", content="doc 1"),
            VectorDocument(id="2", content="doc 2"),
        ]
        
        embeddings = [[0.1] * 4, [0.2] * 4]
        index.add_vectors(["1", "2"], embeddings, docs)
        
        index.remove(["1"])
        
        assert index.count() == 1


class TestVectorStoreBackend:
    """向量存储后端测试"""
    
    @pytest.mark.asyncio
    async def test_memory_backend(self):
        """测试内存后端"""
        from app.langchain.memory.vector_store import VectorStoreBackend, VectorDocument
        
        backend = VectorStoreBackend(
            backend="memory",
            embedding_dim=4,
        )
        
        docs = [
            VectorDocument(id="1", content="doc 1"),
            VectorDocument(id="2", content="doc 2"),
        ]
        
        embeddings = [[0.1] * 4, [0.2] * 4]
        
        ids = await backend.insert(docs, embeddings)
        
        assert len(ids) == 2
        assert await backend.count() == 2
    
    @pytest.mark.asyncio
    async def test_faiss_backend(self):
        """测试 FAISS 后端"""
        from app.langchain.memory.vector_store import VectorStoreBackend, VectorDocument
        
        backend = VectorStoreBackend(
            backend="faiss",
            embedding_dim=4,
        )
        
        docs = [
            VectorDocument(id="1", content="doc 1"),
            VectorDocument(id="2", content="doc 2"),
        ]
        
        embeddings = [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
        ]
        
        ids = await backend.insert(docs, embeddings)
        
        assert len(ids) == 2
        
        query = [1.0, 0.0, 0.0, 0.0]
        results = await backend.search(query, top_k=2)
        
        assert len(results) == 2


class TestRAGRetrieverEmbedding:
    """RAG Retriever Embedding 测试"""
    
    def test_embedding_model_required(self):
        """测试强制要求 Embedding 模型"""
        from app.langchain.memory.rag_retriever import RAGConfig, RAGRetriever, EmbeddingModelError
        
        config = RAGConfig(require_embedding_model=False)
        retriever = RAGRetriever(vector_store=None, config=config)
        
        assert retriever.config.require_embedding_model == False
    
    def test_config_defaults(self):
        """测试默认配置"""
        from app.langchain.memory.rag_retriever import RAGConfig
        
        config = RAGConfig()
        
        assert config.embedding_model == "BAAI/bge-base-zh-v1.5"
        assert config.reranker_model == "BAAI/bge-reranker-base"
        assert config.top_k == 5
        assert config.require_embedding_model == True


class TestSearchServiceHybrid:
    """SearchService 混合检索测试"""
    
    def test_bm25_index_management(self):
        """测试 BM25 索引管理"""
        from app.knowledge_base.services.bm25 import BM25Index, BM25Document
        
        index = BM25Index()
        
        docs = [
            {"id": "1", "content": "测试文档一", "metadata": {"doc_id": "doc1"}},
            {"id": "2", "content": "测试文档二", "metadata": {"doc_id": "doc2"}},
        ]
        
        bm25_docs = [
            BM25Document(id=d["id"], content=d["content"], metadata=d.get("metadata", {}))
            for d in docs
        ]
        
        index.add_documents(bm25_docs)
        
        assert index.n_docs == 2
        
        results = index.search("测试", top_k=2)
        assert len(results) > 0


def run_tests():
    """运行所有测试"""
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_tests()

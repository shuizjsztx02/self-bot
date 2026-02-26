"""
RAG 系统全链路测试

测试内容：
1. 模块导入验证
2. 服务初始化验证
3. 检索流程验证
4. Agent 集成验证
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_module_imports():
    """测试模块导入"""
    print("\n=== 1. 模块导入测试 ===")
    
    errors = []
    
    try:
        from app.langchain.agents.rag_agent import RagAgent
        print("  ✅ RagAgent")
    except Exception as e:
        errors.append(f"RagAgent: {e}")
        print(f"  ❌ RagAgent: {e}")
    
    try:
        from app.knowledge_base.services import (
            SearchService, EmbeddingService, PermissionService,
            BM25Index, ContextCompressor
        )
        print("  ✅ 知识库服务")
    except Exception as e:
        errors.append(f"知识库服务: {e}")
        print(f"  ❌ 知识库服务: {e}")
    
    try:
        from app.langchain.routers import (
            IntentClassifier, QueryRewriter, MultiTurnRAGManager
        )
        print("  ✅ 路由模块")
    except Exception as e:
        errors.append(f"路由模块: {e}")
        print(f"  ❌ 路由模块: {e}")
    
    try:
        from app.knowledge_base.vector_store import VectorStoreFactory
        print("  ✅ 向量存储")
    except Exception as e:
        errors.append(f"向量存储: {e}")
        print(f"  ❌ 向量存储: {e}")
    
    try:
        from app.core.exceptions import (
            EmbeddingError, RetrievalError, ParsingError
        )
        print("  ✅ 异常类")
    except Exception as e:
        errors.append(f"异常类: {e}")
        print(f"  ❌ 异常类: {e}")
    
    return len(errors) == 0


async def test_service_initialization():
    """测试服务初始化"""
    print("\n=== 2. 服务初始化测试 ===")
    
    errors = []
    
    try:
        from app.knowledge_base.services.bm25 import BM25Index, BM25Document
        
        index = BM25Index()
        docs = [
            BM25Document(id="1", content="测试文档一"),
            BM25Document(id="2", content="测试文档二"),
        ]
        index.add_documents(docs)
        
        results = index.search("测试", top_k=2)
        assert len(results) > 0, "BM25 搜索结果为空"
        print("  ✅ BM25Index")
    except Exception as e:
        errors.append(f"BM25Index: {e}")
        print(f"  ❌ BM25Index: {e}")
    
    try:
        from app.langchain.routers.query_rewriter import (
            QueryRewriter, ConversationHistoryManager
        )
        
        rewriter = QueryRewriter()
        result = await rewriter.rewrite("测试查询")
        assert result.rewritten_query is not None
        print("  ✅ QueryRewriter")
    except Exception as e:
        errors.append(f"QueryRewriter: {e}")
        print(f"  ❌ QueryRewriter: {e}")
    
    try:
        from app.knowledge_base.services.compression import ContextCompressor
        
        compressor = ContextCompressor()
        print("  ✅ ContextCompressor")
    except Exception as e:
        errors.append(f"ContextCompressor: {e}")
        print(f"  ❌ ContextCompressor: {e}")
    
    try:
        from app.langchain.routers.multi_turn_rag import MultiTurnRAGManager
        
        manager = MultiTurnRAGManager()
        manager.add_user_message("测试消息")
        history = manager.get_history()
        assert len(history) == 1
        print("  ✅ MultiTurnRAGManager")
    except Exception as e:
        errors.append(f"MultiTurnRAGManager: {e}")
        print(f"  ❌ MultiTurnRAGManager: {e}")
    
    return len(errors) == 0


async def test_intent_classification():
    """测试意图分类"""
    print("\n=== 3. 意图分类测试 ===")
    
    try:
        from app.langchain.routers.intent_classifier import IntentClassifier, QueryIntent
        
        classifier = IntentClassifier()
        
        test_cases = [
            ("公司的报销流程是什么？", QueryIntent.KB_QUERY),
            ("今天天气怎么样？", QueryIntent.GENERAL_CHAT),
            ("帮我写一个 Python 函数", QueryIntent.CODE_TASK),
        ]
        
        success = 0
        for query, expected_intent in test_cases:
            result = classifier.classify(query)
            if result.intent == expected_intent:
                success += 1
                print(f"  ✅ '{query[:20]}...' -> {result.intent.value}")
            else:
                print(f"  ⚠️ '{query[:20]}...' -> {result.intent.value} (期望: {expected_intent.value})")
        
        return success >= 2
    except Exception as e:
        print(f"  ❌ 意图分类测试失败: {e}")
        return False


async def test_rag_agent_creation():
    """测试 RagAgent 创建"""
    print("\n=== 4. RagAgent 创建测试 ===")
    
    try:
        from app.langchain.agents.rag_agent import RagAgent
        
        agent = RagAgent(user_id="test_user")
        print("  ✅ RagAgent 实例创建成功")
        
        tool = agent.as_tool()
        assert tool.name == "rag_search"
        print("  ✅ RagAgent.as_tool() 封装成功")
        
        return True
    except Exception as e:
        print(f"  ❌ RagAgent 创建失败: {e}")
        return False


async def test_vector_store():
    """测试向量存储"""
    print("\n=== 5. 向量存储测试 ===")
    
    try:
        from app.langchain.memory.vector_store import (
            VectorStoreBackend, VectorDocument, InMemoryVectorStore
        )
        
        store = InMemoryVectorStore(embedding_dim=4)
        
        docs = [
            VectorDocument(id="1", content="测试文档一"),
            VectorDocument(id="2", content="测试文档二"),
        ]
        
        embeddings = [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]]
        
        await store.insert(docs, embeddings)
        count = await store.count()
        assert count == 2
        
        results = await store.search([0.1, 0.2, 0.3, 0.4], top_k=2)
        assert len(results) > 0
        
        print("  ✅ InMemoryVectorStore")
        return True
    except Exception as e:
        print(f"  ❌ 向量存储测试失败: {e}")
        return False


async def test_source_attribution():
    """测试引用溯源"""
    print("\n=== 6. 引用溯源测试 ===")
    
    try:
        from app.knowledge_base.services.attribution import (
            SourceAttribution, SourceReference, RAGResponse
        )
        
        attribution = SourceAttribution()
        
        response = RAGResponse(
            answer="这是测试回答",
            sources=[
                SourceReference(
                    doc_id="1",
                    chunk_id="c1",
                    content="来源内容",
                    score=0.9,
                    doc_name="测试文档"
                )
            ],
            segments=[],
            overall_confidence=0.85,
            query="测试问题"
        )
        
        formatted = response.get_formatted_answer(include_citations=True)
        assert "参考来源" in formatted
        
        print("  ✅ SourceAttribution")
        return True
    except Exception as e:
        print(f"  ❌ 引用溯源测试失败: {e}")
        return False


async def main():
    """运行所有测试"""
    print("=" * 60)
    print("RAG 系统全链路测试")
    print("=" * 60)
    
    results = []
    
    results.append(("模块导入", await test_module_imports()))
    results.append(("服务初始化", await test_service_initialization()))
    results.append(("意图分类", await test_intent_classification()))
    results.append(("RagAgent创建", await test_rag_agent_creation()))
    results.append(("向量存储", await test_vector_store()))
    results.append(("引用溯源", await test_source_attribution()))
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = 0
    failed = 0
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

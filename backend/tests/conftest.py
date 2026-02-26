"""
测试配置

提供测试所需的公共fixtures和配置
"""
import pytest
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db_session():
    """模拟数据库会话"""
    from unittest.mock import AsyncMock, Mock
    
    db = AsyncMock()
    db.execute = AsyncMock()
    db.scalar_one_or_none = Mock(return_value=None)
    db.scalars = Mock(return_value=Mock(all=Mock(return_value=[])))
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.add = Mock()
    db.delete = Mock()
    
    return db


@pytest.fixture
def mock_llm():
    """模拟LLM客户端"""
    from unittest.mock import Mock, AsyncMock
    
    llm = Mock()
    llm.ainvoke = AsyncMock(return_value=Mock(content='{"result": "test"}'))
    llm.invoke = Mock(return_value=Mock(content='{"result": "test"}'))
    
    return llm


@pytest.fixture
def mock_embedding_service():
    """模拟嵌入服务"""
    from unittest.mock import Mock, AsyncMock
    
    service = Mock()
    service.embed_text = AsyncMock(return_value=[0.1] * 768)
    service.embed_batch = AsyncMock(return_value=[[0.1] * 768])
    
    return service


@pytest.fixture
def mock_search_service():
    """模拟搜索服务"""
    from unittest.mock import Mock, AsyncMock
    from dataclasses import dataclass
    
    @dataclass
    class MockSearchResult:
        chunk_id: str
        content: str
        score: float
        doc_name: str = "test_doc"
        kb_name: str = "test_kb"
    
    service = Mock()
    service.search = AsyncMock(return_value=[
        MockSearchResult(chunk_id="1", content="测试内容", score=0.9),
    ])
    service.hybrid_search = AsyncMock(return_value=[
        MockSearchResult(chunk_id="1", content="测试内容", score=0.9),
    ])
    
    return service

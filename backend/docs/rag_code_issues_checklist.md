# RAG/知识库模块代码修改需求清单

## 问题统计总览

| 严重程度 | 数量 | 说明 |
|---------|------|------|
| 🔴 高 | 12 | 影响功能正确性、数据一致性 |
| 🟡 中 | 12 | 影响代码质量、可维护性 |
| 🟢 低 | 6 | 代码规范、优化类问题 |
| **总计** | **30** | |

---

## 一、架构设计问题（7项）

### 1.1 🔴 服务实例重复创建
**优先级**: P0  
**文件**: `backend/app/knowledge_base/routes/documents.py`  
**行号**: 121-127, 160-166, 232-238 等多处

**问题描述**:
每个路由函数都重复创建 `VectorStoreFactory.create("chroma")`、`EmbeddingService()` 和 `DocumentService` 实例，导致：
- 资源浪费（每次请求都创建新实例）
- Embedding模型重复加载（耗时约5-10秒）
- 缓存失效

**当前代码**:
```python
# documents.py 多处重复代码
vector_store = VectorStoreFactory.create("chroma")
embedding_service = EmbeddingService()
doc_service = DocumentService(
    db=db,
    vector_store=vector_store,
    embedding_service=embedding_service,
)
```

**修改方案**:
```python
# 1. 创建服务依赖注入模块
# backend/app/knowledge_base/dependencies.py

from functools import lru_cache
from fastapi import Depends

@lru_cache()
def get_vector_store() -> VectorStoreBackend:
    return VectorStoreFactory.create("chroma")

@lru_cache()
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()

async def get_document_service(
    db: AsyncSession = Depends(get_async_session),
    vector_store: VectorStoreBackend = Depends(get_vector_store),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> DocumentService:
    return DocumentService(db, vector_store, embedding_service)

# 2. 在路由中使用依赖注入
@router.post("/upload")
async def upload_document(
    doc_service: DocumentService = Depends(get_document_service),
):
    ...
```

---

### 1.2 🔴 全局变量线程安全问题
**优先级**: P0  
**文件**: `backend/app/knowledge_base/dependencies.py`  
**行号**: 9-11

**问题描述**:
使用全局变量存储服务实例，在多线程/多进程环境下可能导致竞态条件。

**当前代码**:
```python
_vector_store_instance = None
_embedding_service_instance = None
_bm25_indexes: dict = {}
```

**修改方案**:
```python
# 方案1: 使用 FastAPI app.state
# main.py
@app.on_event("startup")
async def startup_event():
    app.state.vector_store = VectorStoreFactory.create("chroma")
    app.state.embedding_service = EmbeddingService()
    app.state.bm25_indexes = {}

# dependencies.py
from fastapi import Request

def get_vector_store(request: Request) -> VectorStoreBackend:
    return request.app.state.vector_store

# 方案2: 使用线程安全的单例模式
import threading

class ServiceManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._vector_store = None
                    cls._instance._embedding_service = None
        return cls._instance
```

---

### 1.3 🔴 向量存储抽象不一致
**优先级**: P0  
**文件**: 
- `backend/app/knowledge_base/vector_store/__init__.py`
- `backend/app/langchain/memory/vector_store.py`

**问题描述**:
存在两套不同的向量存储实现，接口不一致：
- `knowledge_base/vector_store/__init__.py` - `VectorStoreBackend` 抽象类
- `langchain/memory/vector_store.py` - `VectorStoreBackend` 类

**修改方案**:
```python
# 统一到 backend/app/core/vector_store/base.py

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class VectorStoreBackend(ABC):
    """向量存储后端抽象基类"""
    
    @abstractmethod
    async def create_collection(self, name: str, dimension: int) -> bool:
        """创建集合"""
        pass
    
    @abstractmethod
    async def add_vectors(
        self,
        collection_name: str,
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
    ) -> bool:
        """添加向量"""
        pass
    
    @abstractmethod
    async def search(
        self,
        collection_name: str,
        query_embedding: List[float],
        top_k: int = 10,
        filter: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """搜索相似向量"""
        pass
    
    @abstractmethod
    async def delete_by_ids(self, collection_name: str, ids: List[str]) -> bool:
        """删除向量"""
        pass
    
    @abstractmethod
    async def delete_collection(self, name: str) -> bool:
        """删除集合"""
        pass
```

---

### 1.4 🟡 重复的枚举定义
**优先级**: P1  
**文件**: `backend/app/knowledge_base/schemas.py`  
**行号**: 9-14

**问题描述**:
`KBRoleEnum` 在 schemas.py 中重复定义，而 models.py 中已有 `KBRole` 枚举。

**当前代码**:
```python
# schemas.py
class KBRoleEnum(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"

# models.py
class KBRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
```

**修改方案**:
```python
# schemas.py - 删除 KBRoleEnum，统一使用 models.KBRole
from app.knowledge_base.models import KBRole

# 所有使用 KBRoleEnum 的地方改为 KBRole
class PermissionGrant(BaseModel):
    user_id: Optional[str] = None
    group_id: Optional[str] = None
    role: KBRole  # 使用 models.KBRole
    folder_id: Optional[str] = None
    expires_at: Optional[datetime] = None
```

---

### 1.5 🟡 查询重写模块未集成
**优先级**: P1  
**文件**: `backend/app/langchain/routers/multi_turn_rag.py`

**问题描述**:
`MultiTurnRAGManager` 和 `QueryRewriter` 模块已实现，但未在 `RagAgent` 中使用。

**修改方案**:
```python
# backend/app/langchain/agents/rag_agent.py

from app.langchain.routers.multi_turn_rag import MultiTurnRAGManager

class RagAgent:
    def __init__(self, ...):
        ...
        self._multi_turn_manager: Optional[MultiTurnRAGManager] = None
    
    @property
    def multi_turn_manager(self) -> MultiTurnRAGManager:
        if self._multi_turn_manager is None:
            self._multi_turn_manager = MultiTurnRAGManager(
                embedding_service=self.embedding_service,
            )
        return self._multi_turn_manager
    
    async def chat(self, message: str, conversation_id: Optional[str] = None):
        # 如果有对话历史，进行查询重写
        if conversation_id:
            rewritten_query = await self.multi_turn_manager.rewrite_query(
                message, 
                conversation_id
            )
            message = rewritten_query
        
        # 继续正常流程...
```

---

### 1.6 🟡 并行路由流式输出简化过度
**优先级**: P1  
**文件**: `backend/app/langchain/agents/supervisor_agent.py`  
**行号**: 496-518

**问题描述**:
并行路由的流式输出只选择第一个路由执行，失去了并行路由的意义。

**修改方案**:
```python
async def _parallel_route_stream(
    self,
    message: str,
    routes: List[str],
    ...
):
    """真正的并行路由流式执行"""
    import asyncio
    
    async def execute_route(route: str):
        async for event in self._route_stream(route, message):
            yield {"route": route, "event": event}
    
    # 创建所有路由的生成器
    generators = [execute_route(route) for route in routes]
    
    # 使用 asyncio.merge 合并流
    async for result in self._merge_streams(generators):
        yield result

async def _merge_streams(self, generators):
    """合并多个异步生成器"""
    pending = set()
    for gen in generators:
        pending.add(asyncio.create_task(gen.__anext__()))
    
    while pending:
        done, pending = await asyncio.wait(
            pending, 
            return_when=asyncio.FIRST_COMPLETED
        )
        for task in done:
            try:
                yield task.result()
                # 重新添加生成器的下一个任务
                pending.add(asyncio.create_task(gen.__anext__()))
            except StopAsyncIteration:
                pass
```

---

### 1.7 🟢 意图分类器硬编码关键词
**优先级**: P2  
**文件**: `backend/app/langchain/routers/intent_classifier.py`  
**行号**: 137-152

**问题描述**:
`KB_KEYWORDS` 硬编码了知识库名称映射，新增知识库需要修改代码。

**修改方案**:
```python
class IntentClassifier:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._kb_keywords: Optional[Dict[str, List[str]]] = None
    
    async def _load_kb_keywords(self) -> Dict[str, List[str]]:
        """从数据库动态加载知识库关键词"""
        from app.knowledge_base.models import KnowledgeBase
        
        result = await self.db.execute(
            select(KnowledgeBase.id, KnowledgeBase.name, KnowledgeBase.description)
        )
        kbs = result.scalars().all()
        
        keywords = {}
        for kb in kbs:
            # 使用知识库名称和描述作为关键词
            name = kb.name
            keywords[name] = [kb.id]
            
            # 可以扩展：从知识库元数据读取自定义关键词
            # if kb.metadata and 'keywords' in kb.metadata:
            #     for kw in kb.metadata['keywords']:
            #         keywords[kw] = [kb.id]
        
        return keywords
```

---

## 二、数据流问题（5项）

### 2.1 🔴 BM25索引未与数据库同步
**优先级**: P0  
**文件**: `backend/app/knowledge_base/services/search.py`  
**行号**: 261-266

**问题描述**:
`SearchService` 的 `_bm25_indexes` 是内存字典，服务重启后索引丢失。

**修改方案**:
```python
# 方案1: 服务启动时重建索引
# backend/app/knowledge_base/services/search.py

class SearchService:
    def __init__(self, db: AsyncSession, ...):
        self.db = db
        self._bm25_indexes: Dict[str, BM25Index] = {}
        self._bm25_index_path = settings.BM25_INDEX_PATH
    
    async def initialize(self):
        """初始化时加载或重建BM25索引"""
        import os
        
        if os.path.exists(self._bm25_index_path):
            # 尝试从磁盘加载
            await self._load_indexes_from_disk()
        else:
            # 从数据库重建
            await self._rebuild_all_indexes()
    
    async def _rebuild_all_indexes(self):
        """从数据库重建所有知识库的BM25索引"""
        from app.knowledge_base.models import KnowledgeBase, Document, DocumentChunk
        
        result = await self.db.execute(select(KnowledgeBase))
        kbs = result.scalars().all()
        
        for kb in kbs:
            await self._rebuild_kb_index(kb.id)
    
    async def _rebuild_kb_index(self, kb_id: str):
        """重建单个知识库的BM25索引"""
        from app.knowledge_base.models import DocumentChunk
        
        result = await self.db.execute(
            select(DocumentChunk).where(DocumentChunk.kb_id == kb_id)
        )
        chunks = result.scalars().all()
        
        if chunks:
            index = BM25Index()
            index.add_documents([
                BM25Document(
                    id=chunk.id,
                    content=chunk.content,
                    metadata={"doc_id": chunk.doc_id}
                )
                for chunk in chunks
            ])
            self._bm25_indexes[kb_id] = index

# 在应用启动时调用
# main.py
@app.on_event("startup")
async def startup_event():
    search_service = SearchService(db)
    await search_service.initialize()
```

---

### 2.2 🔴 文档处理后台任务缺少错误恢复
**优先级**: P0  
**文件**: `backend/app/knowledge_base/routes/documents.py`  
**行号**: 25-86

**问题描述**:
`process_document` 后台任务在失败时只记录错误，没有重试机制。

**修改方案**:
```python
# backend/app/knowledge_base/services/document_processor.py

from tenacity import retry, stop_after_attempt, wait_exponential

class DocumentProcessor:
    def __init__(self, db: AsyncSession, ...):
        self.db = db
        self.max_retries = 3
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        reraise=True,
    )
    async def process_with_retry(self, doc_id: str, kb_id: str, file_path: str):
        """带重试的文档处理"""
        try:
            await self._process_document(doc_id, kb_id, file_path)
        except Exception as e:
            # 记录重试信息
            logger.warning(f"Document processing failed, retrying: {doc_id}, error: {e}")
            raise
    
    async def _process_document(self, doc_id: str, kb_id: str, file_path: str):
        """实际处理逻辑"""
        ...

# 使用 Celery 或 arq 实现任务队列（推荐）
# backend/app/workers/tasks.py

from arq import create_pool
from arq.connections import RedisSettings

async def process_document_task(ctx, doc_id: str, kb_id: str, file_path: str):
    """异步任务处理文档"""
    async with AsyncSessionLocal() as db:
        processor = DocumentProcessor(db)
        await processor.process_with_retry(doc_id, kb_id, file_path)

# Worker 配置
class WorkerSettings:
    functions = [process_document_task]
    redis_settings = RedisSettings(host='localhost', port=6379)
    max_tries = 3
```

---

### 2.3 🟡 检索结果缺少去重
**优先级**: P1  
**文件**: `backend/app/knowledge_base/services/search.py`  
**行号**: 98-128

**问题描述**:
`cross_search` 方法在合并多个知识库结果时，没有对相同 chunk_id 的结果去重。

**修改方案**:
```python
async def cross_search(
    self,
    kb_ids: List[str],
    query: str,
    top_k: int = 10,
    ...
) -> List[SearchResult]:
    """跨知识库搜索（带去重）"""
    
    all_results = []
    seen_chunk_ids = set()
    
    for kb_id in kb_ids:
        results = await self.search(kb_id, query, top_k=top_k)
        for result in results:
            if result.chunk_id not in seen_chunk_ids:
                all_results.append(result)
                seen_chunk_ids.add(result.chunk_id)
    
    # 按分数排序并返回 top_k
    all_results.sort(key=lambda x: x.score, reverse=True)
    return all_results[:top_k]
```

---

### 2.4 🟡 缺少输入验证
**优先级**: P1  
**文件**: `backend/app/knowledge_base/services/search.py`  
**行号**: 49-96

**问题描述**:
`search` 方法没有验证 `kb_id` 是否存在或有效。

**修改方案**:
```python
async def search(
    self,
    kb_id: str,
    query: str,
    ...
) -> List[SearchResult]:
    """搜索（带输入验证）"""
    
    # 验证知识库存在
    from app.knowledge_base.models import KnowledgeBase
    
    kb_result = await self.db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    )
    kb = kb_result.scalar_one_or_none()
    
    if kb is None:
        raise ValueError(f"Knowledge base not found: {kb_id}")
    
    if not kb.is_active:
        raise ValueError(f"Knowledge base is inactive: {kb_id}")
    
    # 验证查询长度
    if not query or len(query.strip()) == 0:
        raise ValueError("Query cannot be empty")
    
    if len(query) > 1000:
        raise ValueError("Query too long (max 1000 characters)")
    
    # 继续正常搜索流程...
```

---

### 2.5 🟢 知识库嵌入缓存无过期
**优先级**: P2  
**文件**: `backend/app/langchain/routers/kb_router.py`  
**行号**: 97-101

**问题描述**:
`_kb_embeddings` 缓存没有过期机制，知识库描述更新后缓存不会刷新。

**修改方案**:
```python
from cachetools import TTLCache

class KBRouter:
    def __init__(self, db: AsyncSession):
        self.db = db
        # 使用 TTL 缓存，1小时过期
        self._kb_embeddings = TTLCache(maxsize=100, ttl=3600)
    
    async def get_kb_embedding(self, kb_id: str) -> List[float]:
        """获取知识库嵌入（带TTL缓存）"""
        if kb_id in self._kb_embeddings:
            return self._kb_embeddings[kb_id]
        
        kb = await self._get_kb(kb_id)
        kb_text = f"{kb.name}\n{kb.description or ''}"
        embedding = await self.embedding_service.embed_text(kb_text)
        
        self._kb_embeddings[kb_id] = embedding
        return embedding
    
    def invalidate_cache(self, kb_id: str):
        """使缓存失效"""
        if kb_id in self._kb_embeddings:
            del self._kb_embeddings[kb_id]
```

---

## 三、错误处理问题（4项）

### 3.1 🔴 异常处理过于宽泛
**优先级**: P0  
**文件**: `backend/app/knowledge_base/vector_store/__init__.py`  
**行号**: 103-106, 123

**问题描述**:
使用空的 `except` 或过于宽泛的异常捕获，隐藏了真实错误。

**当前代码**:
```python
except Exception as e:
    print(f"Error creating collection: {e}")
    return False

except:  # 裸 except
    return False
```

**修改方案**:
```python
import logging

logger = logging.getLogger(__name__)

class VectorStoreError(Exception):
    """向量存储错误基类"""
    pass

class CollectionCreationError(VectorStoreError):
    """集合创建错误"""
    pass

class VectorSearchError(VectorStoreError):
    """向量搜索错误"""
    pass

# 使用具体异常类型
async def create_collection(self, name: str, dimension: int) -> bool:
    try:
        collection = self._client.create_collection(
            name=name,
            metadata={"dimension": dimension}
        )
        return True
    except chromadb.Error as e:
        logger.error(f"ChromaDB error creating collection {name}: {e}")
        raise CollectionCreationError(f"Failed to create collection: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error creating collection {name}")
        raise CollectionCreationError(f"Unexpected error: {e}")
```

---

### 3.2 🔴 RAG Agent 服务初始化问题
**优先级**: P0  
**文件**: `backend/app/langchain/agents/rag_agent.py`  
**行号**: 40-60

**问题描述**:
使用 `async for` 获取 session 后 `break`，可能导致资源泄漏。

**当前代码**:
```python
if self.db_session is None:
    async for session in get_async_session():
        self.db_session = session
        break
```

**修改方案**:
```python
# 方案1: 使用依赖注入，不自己创建 session
class RagAgent:
    def __init__(
        self,
        db_session: AsyncSession,
        embedding_service: Optional[EmbeddingService] = None,
        ...
    ):
        self.db_session = db_session
        self._embedding_service = embedding_service
        ...

# 方案2: 如果必须自己创建，使用上下文管理器
async def _get_services(self):
    if self.db_session is None:
        # 使用 async with 确保正确管理
        async with AsyncSessionLocal() as session:
            self.db_session = session
            # 注意：这种方式 session 会在退出上下文后关闭
```

---

### 3.3 🔴 文档删除时向量未完全清理
**优先级**: P0  
**文件**: `backend/app/knowledge_base/services/document.py`  
**行号**: 318-329

**问题描述**:
`clear_chunks` 方法使用 `delete_by_ids` 删除向量，但传入的是 `chunk.id` 而非 `vector_id`。

**当前代码**:
```python
if chunk_ids:
    collection_name = f"kb_{doc.kb_id.replace('-', '_')}"
    try:
        await self.vector_store.delete_by_ids(collection_name, chunk_ids)
    except Exception:
        pass
```

**修改方案**:
```python
async def clear_chunks(self, doc_id: str) -> List[str]:
    """清除文档的所有分块（正确删除向量）"""
    
    result = await self.db.execute(
        select(DocumentChunk).where(DocumentChunk.doc_id == doc_id)
    )
    chunks = result.scalars().all()
    
    if not chunks:
        return []
    
    # 获取正确的向量ID
    vector_ids = []
    chunk_ids = []
    
    for chunk in chunks:
        chunk_ids.append(chunk.id)
        # 使用存储在 chunk 中的 vector_id，如果没有则使用 chunk.id
        vector_ids.append(getattr(chunk, 'vector_id', chunk.id))
    
    # 删除向量
    if vector_ids:
        collection_name = f"kb_{doc.kb_id.replace('-', '_')}"
        try:
            await self.vector_store.delete_by_ids(collection_name, vector_ids)
        except Exception as e:
            logger.error(f"Failed to delete vectors for doc {doc_id}: {e}")
            # 继续删除数据库记录
    
    # 删除数据库记录
    for chunk in chunks:
        await self.db.delete(chunk)
    
    await self.db.commit()
    
    return chunk_ids
```

---

### 3.4 🟡 Optional类型处理不当
**优先级**: P1  
**文件**: `backend/app/knowledge_base/services/search.py`  
**行号**: 36-47

**问题描述**:
`reranker` 属性可能返回 `None`，但调用处没有始终检查。

**修改方案**:
```python
from typing import Optional
from sentence_transformers import CrossEncoder

class SearchService:
    _reranker: Optional[CrossEncoder] = None
    
    @property
    def reranker(self) -> Optional[CrossEncoder]:
        """获取重排序模型（可能为None）"""
        if self._reranker is None:
            try:
                from sentence_transformers import CrossEncoder
                self._reranker = CrossEncoder(self.reranker_model)
            except ImportError:
                logger.warning("sentence-transformers not installed, reranking disabled")
            except Exception as e:
                logger.warning(f"Failed to load reranker: {e}")
        return self._reranker
    
    async def rerank(
        self,
        query: str,
        results: List[SearchResult],
        top_k: int = 10,
    ) -> List[SearchResult]:
        """重排序（安全调用）"""
        reranker = self.reranker
        
        if reranker is None:
            # 重排序不可用，直接返回原结果
            logger.info("Reranker not available, returning original results")
            return results[:top_k]
        
        # 执行重排序...
```

---

## 四、性能问题（4项）

### 4.1 🔴 N+1查询问题
**优先级**: P0  
**文件**: `backend/app/knowledge_base/routes/search.py`  
**行号**: 77-89

**问题描述**:
在搜索结果中逐个查询文档名称，造成 N+1 查询问题。

**当前代码**:
```python
for result in results:
    doc_result = await db.execute(
        select(Document).where(Document.id == result.doc_id)
    )
    doc = doc_result.scalar_one_or_none()
```

**修改方案**:
```python
async def search_knowledge_base(
    kb_id: str,
    request: SearchRequest,
    ...
):
    # 执行搜索
    results = await search_service.search(kb_id, request.query, ...)
    
    if not results:
        return SearchResponse(results=[], total=0, query=request.query)
    
    # 批量查询所有文档
    doc_ids = list(set(r.doc_id for r in results))
    
    doc_result = await db.execute(
        select(Document).where(Document.id.in_(doc_ids))
    )
    docs = {doc.id: doc for doc in doc_result.scalars().all()}
    
    # 组装结果
    for result in results:
        doc = docs.get(result.doc_id)
        if doc:
            result.doc_name = doc.filename
    
    return SearchResponse(results=results, ...)
```

---

### 4.2 🟡 Embedding缓存无限制增长
**优先级**: P1  
**文件**: `backend/app/knowledge_base/services/embedding.py`  
**行号**: 17

**问题描述**:
`_cache` 字典没有大小限制，可能导致内存泄漏。

**修改方案**:
```python
from cachetools import LRUCache

class EmbeddingService:
    def __init__(
        self,
        model_name: str = None,
        cache_enabled: bool = True,
        cache_size: int = 10000,
    ):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self._model = None
        
        # 使用 LRU 缓存替代无限字典
        if cache_enabled:
            self._cache = LRUCache(maxsize=cache_size)
        else:
            self._cache = None
    
    async def embed_text(self, text: str) -> List[float]:
        # 生成缓存键
        cache_key = hashlib.md5(text.encode()).hexdigest()
        
        # 检查缓存
        if self._cache is not None and cache_key in self._cache:
            return self._cache[cache_key]
        
        # 计算嵌入
        loop = asyncio.get_running_loop()
        embedding = await loop.run_in_executor(
            None,
            self._embed_sync,
            text
        )
        
        # 存入缓存
        if self._cache is not None:
            self._cache[cache_key] = embedding
        
        return embedding
```

---

### 4.3 🟡 同步阻塞调用
**优先级**: P1  
**文件**: `backend/app/knowledge_base/services/search.py`  
**行号**: 140-145

**问题描述**:
使用 `asyncio.get_event_loop()` 已被弃用。

**当前代码**:
```python
loop = asyncio.get_event_loop()
scores = await loop.run_in_executor(
    None,
    self.reranker.predict,
    pairs,
)
```

**修改方案**:
```python
# Python 3.9+
scores = await asyncio.to_thread(
    self.reranker.predict,
    pairs,
)

# Python 3.7-3.8 兼容写法
loop = asyncio.get_running_loop()
scores = await loop.run_in_executor(
    None,
    self.reranker.predict,
    pairs,
)
```

---

### 4.4 🟢 硬编码的默认值
**优先级**: P2  
**文件**: 多个文件

**问题描述**:
多处硬编码默认值，与配置系统不一致。

**修改方案**:
```python
# 统一从 settings 读取

# models.py
from app.config import settings

class KnowledgeBase(Base):
    embedding_model = Column(
        String(200),
        default=settings.EMBEDDING_MODEL  # 从配置读取
    )

# search.py
class SearchService:
    def __init__(
        self,
        db: AsyncSession,
        reranker_model: str = None,  # 改为可选参数
    ):
        self.reranker_model = reranker_model or settings.RERANKER_MODEL
```

---

## 五、接口设计问题（3项）

### 5.1 🟡 API响应不一致
**优先级**: P1  
**文件**: `backend/app/knowledge_base/routes/documents.py`  
**行号**: 347-349

**问题描述**:
`reprocess_document` 函数传递了多余的 `db` 参数。

**当前代码**:
```python
background_tasks.add_task(
    process_document,
    doc_id,
    doc.kb_id,
    doc.file_path,
    db,  # 多余的参数
)
```

**修改方案**:
```python
# 检查 process_document 的签名
async def process_document(doc_id: str, kb_id: str, file_path: str):
    ...

# 移除多余参数
background_tasks.add_task(
    process_document,
    doc_id,
    doc.kb_id,
    doc.file_path,
)
```

---

### 5.2 🟡 权限检查类型不一致
**优先级**: P1  
**文件**: `backend/app/knowledge_base/routes/documents.py`  
**行号**: 103-104

**问题描述**:
权限检查使用字符串 `"editor"` 而非枚举 `KBRole.EDITOR`。

**修改方案**:
```python
from app.knowledge_base.models import KBRole

# 统一使用枚举
has_permission = await permission_service.has_permission(
    current_user.id, kb_id, KBRole.EDITOR
)
```

---

### 5.3 🟢 缺少分页参数验证
**优先级**: P2  
**文件**: `backend/app/knowledge_base/routes/knowledge_bases.py`  
**行号**: 41-42

**问题描述**:
分页参数 `skip` 和 `limit` 在服务层没有再次验证。

**修改方案**:
```python
# services/knowledge_base.py
async def list_all(
    self,
    skip: int = 0,
    limit: int = 100,
    owner_id: Optional[str] = None,
) -> List[KnowledgeBase]:
    # 添加边界检查
    skip = max(0, skip)
    limit = min(max(1, limit), 100)  # 限制最大100
    
    query = select(KnowledgeBase)
    
    if owner_id:
        query = query.where(KnowledgeBase.owner_id == owner_id)
    
    query = query.offset(skip).limit(limit)
    
    result = await self.db.execute(query)
    return list(result.scalars().all())
```

---

## 六、类型定义问题（3项）

### 6.1 🟢 使用Any类型过于宽泛
**优先级**: P2  
**文件**: `backend/app/knowledge_base/services/attribution.py`  
**行号**: 121

**修改方案**:
```python
from typing import Protocol

class EmbeddingServiceProtocol(Protocol):
    """Embedding服务协议"""
    async def embed_text(self, text: str) -> List[float]: ...
    async def embed_batch(self, texts: List[str]) -> List[List[float]]: ...

class AttributionService:
    def __init__(
        self,
        embedding_service: Optional[EmbeddingServiceProtocol] = None,
    ):
        self.embedding_service = embedding_service
```

---

### 6.2 🟢 缺少返回类型注解
**优先级**: P2  
**文件**: `backend/app/knowledge_base/services/bm25.py`

**修改方案**:
```python
def save_to_disk(self, path: str) -> None:
    """保存索引到磁盘"""
    ...

def _load_from_disk(self, path: str) -> None:
    """从磁盘加载索引"""
    ...
```

---

### 6.3 🟢 日志使用不规范
**优先级**: P2  
**文件**: 多个文件

**修改方案**:
```python
# 统一使用 logging
import logging

logger = logging.getLogger(__name__)

# 替换所有 print 为 logger
# print(f"Error...") -> logger.error(f"Error...")
```

---

## 七、测试覆盖问题（4项）

### 7.1 🔴 缺少单元测试
**优先级**: P0

**修改方案**:
创建测试文件结构：
```
backend/tests/
├── unit/
│   ├── knowledge_base/
│   │   ├── test_embedding_service.py
│   │   ├── test_search_service.py
│   │   ├── test_bm25_index.py
│   │   ├── test_document_service.py
│   │   └── test_permission_service.py
│   └── agents/
│       └── test_rag_agent.py
└── integration/
    └── test_rag_flow.py
```

---

### 7.2 🔴 缺少集成测试
**优先级**: P0

**修改方案**:
```python
# tests/integration/test_rag_flow.py

import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_full_rag_flow():
    """测试完整的RAG流程"""
    async with AsyncClient() as client:
        # 1. 创建知识库
        response = await client.post("/api/knowledge-bases", json={
            "name": "测试知识库",
            "description": "用于测试",
        })
        assert response.status_code == 201
        kb_id = response.json()["id"]
        
        # 2. 上传文档
        with open("test.pdf", "rb") as f:
            response = await client.post(
                f"/api/documents/upload",
                files={"file": f},
                data={"kb_id": kb_id},
            )
        assert response.status_code == 201
        doc_id = response.json()["id"]
        
        # 3. 等待处理完成
        # ...
        
        # 4. 搜索
        response = await client.post("/api/search", json={
            "kb_ids": [kb_id],
            "query": "测试查询",
        })
        assert response.status_code == 200
        assert len(response.json()["results"]) > 0
        
        # 5. 清理
        await client.delete(f"/api/knowledge-bases/{kb_id}")
```

---

## 八、实施计划

### 阶段一：紧急修复（1-2周）

| 序号 | 问题 | 预估工时 |
|------|------|----------|
| 1 | 服务实例重复创建 | 4h |
| 2 | 全局变量线程安全 | 4h |
| 3 | BM25索引同步 | 8h |
| 4 | 文档处理错误恢复 | 8h |
| 5 | 异常处理规范化 | 4h |
| 6 | RAG Agent初始化 | 2h |
| 7 | N+1查询优化 | 4h |
| 8 | 向量删除修复 | 2h |

**总计**: 约36小时

### 阶段二：功能完善（2-3周）

| 序号 | 问题 | 预估工时 |
|------|------|----------|
| 1 | 向量存储抽象统一 | 8h |
| 2 | 枚举定义统一 | 2h |
| 3 | 查询重写集成 | 8h |
| 4 | 检索去重 | 2h |
| 5 | 输入验证 | 4h |
| 6 | Embedding缓存优化 | 4h |
| 7 | API响应一致性 | 2h |
| 8 | 权限类型统一 | 2h |

**总计**: 约32小时

### 阶段三：质量提升（1-2周）

| 序号 | 问题 | 预估工时 |
|------|------|----------|
| 1 | 单元测试 | 16h |
| 2 | 集成测试 | 8h |
| 3 | 类型注解完善 | 4h |
| 4 | 日志规范化 | 2h |
| 5 | 配置统一 | 2h |
| 6 | 文档更新 | 4h |

**总计**: 约36小时

---

## 九、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 向量存储重构可能影响现有功能 | 高 | 先添加测试覆盖，再重构 |
| 服务注入改造可能需要大量修改 | 中 | 分阶段进行，保持向后兼容 |
| BM25索引重建可能耗时 | 中 | 添加进度显示，支持增量更新 |
| 测试覆盖不足可能隐藏bug | 高 | 优先添加核心路径测试 |

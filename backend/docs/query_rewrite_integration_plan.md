# 查询重写模块集成方案

## 一、当前状态

### 已实现但未集成的模块

| 模块 | 文件位置 | 功能 |
|------|----------|------|
| QueryRewriter | `routers/query_rewriter.py` | 实体提取、代词解析、查询扩展 |
| MultiTurnRAGManager | `routers/multi_turn_rag.py` | 多轮对话RAG管理 |
| ConversationHistoryManager | `routers/query_rewriter.py` | 对话历史管理 |

### 当前问题

```python
# supervisor_agent.py 第380-405行
async def _rag_enhanced_chat(self, message: str, intent_result: IntentResult, db=None):
    # ❌ 问题1: 直接使用原始查询，没有重写
    # ❌ 问题2: 没有使用对话历史
    # ❌ 问题3: 没有上下文压缩
    
    results = await self.rag_agent.search(
        query=message,  # 原始查询
        kb_ids=kb_ids,
        top_k=5,
    )
```

## 二、集成方案

### 方案A: 最小改动（推荐）

在 `SupervisorAgent` 中添加查询重写，保持现有架构。

```python
# backend/app/langchain/agents/supervisor_agent.py

from app.langchain.routers import QueryRewriter, QueryRewriteConfig

class SupervisorAgent:
    def __init__(self, ...):
        ...
        self._query_rewriter: Optional[QueryRewriter] = None
        self._conversation_history: List[dict] = []
    
    @property
    def query_rewriter(self) -> QueryRewriter:
        if self._query_rewriter is None:
            self._query_rewriter = QueryRewriter(
                config=QueryRewriteConfig(
                    max_history_turns=5,
                    enable_query_expansion=True,
                ),
                llm_client=self._get_llm(),
            )
        return self._query_rewriter
    
    async def _rag_enhanced_chat(
        self,
        message: str,
        intent_result: IntentResult,
        db=None,
    ) -> dict:
        """RAG增强对话（带查询重写）"""
        from app.langchain.routers.query_rewriter import ConversationTurn
        
        # 1. 构建对话历史
        history = [
            ConversationTurn(role=turn["role"], content=turn["content"])
            for turn in self._conversation_history[-5:]
        ]
        
        # 2. 查询重写
        rewritten = await self.query_rewriter.rewrite(message, history)
        
        # 使用重写后的查询
        actual_query = rewritten.rewritten_query
        
        # 3. 执行检索
        kb_ids = intent_result.kb_hints if intent_result.kb_hints else None
        
        # 使用重写查询和变体查询
        all_queries = [actual_query] + rewritten.variations[:2]
        
        all_results = []
        seen_ids = set()
        
        for query in all_queries:
            results = await self.rag_agent.search(
                query=query,
                kb_ids=kb_ids,
                top_k=5,
            )
            for r in results:
                if r.chunk_id not in seen_ids:
                    seen_ids.add(r.chunk_id)
                    all_results.append(r)
        
        # 按分数排序
        all_results.sort(key=lambda x: x.score, reverse=True)
        results = all_results[:10]
        
        # 4. 构建上下文
        if results and results[0].score >= 0.5:
            context = self._build_rag_context(results)
            enhanced_message = f"{context}\n\n用户问题：{message}"
        else:
            enhanced_message = message
        
        # 5. 记录对话历史
        response = await self.main_agent.chat(enhanced_message, db=db)
        
        self._conversation_history.append({"role": "user", "content": message})
        self._conversation_history.append({"role": "assistant", "content": response.get("output", "")})
        
        # 保持历史长度
        if len(self._conversation_history) > 20:
            self._conversation_history = self._conversation_history[-20:]
        
        return response
```

### 方案B: 完整集成（推荐长期）

使用 `MultiTurnRAGManager` 完整集成所有增强功能。

```python
# backend/app/langchain/agents/supervisor_agent.py

from app.langchain.routers import (
    MultiTurnRAGManager,
    MultiTurnRAGConfig,
    MultiTurnRAGPipeline,
)

class SupervisorAgent:
    def __init__(self, ...):
        ...
        self._multi_turn_rag: Optional[MultiTurnRAGManager] = None
    
    @property
    def multi_turn_rag(self) -> MultiTurnRAGManager:
        if self._multi_turn_rag is None:
            self._multi_turn_rag = MultiTurnRAGManager(
                config=MultiTurnRAGConfig(
                    max_history_turns=10,
                    max_context_tokens=4000,
                    enable_query_rewrite=True,
                    enable_compression=True,
                    enable_attribution=True,
                ),
                embedding_service=self._get_embedding_service(),
                search_service=self._get_search_service(),
                llm_client=self._get_llm(),
            )
        return self._multi_turn_rag
    
    async def _rag_enhanced_chat(
        self,
        message: str,
        intent_result: IntentResult,
        db=None,
    ) -> dict:
        """RAG增强对话（完整版）"""
        kb_ids = intent_result.kb_hints if intent_result.kb_hints else None
        
        # 使用 MultiTurnRAGManager 处理完整流程
        async def generate_response(query: str, context: str) -> str:
            return await self.main_agent.chat(
                f"{context}\n\n用户问题：{query}",
                db=db,
            )
        
        response = await self.multi_turn_rag.chat_with_rag(
            query=message,
            kb_ids=kb_ids,
            top_k=5,
            generate_response=generate_response,
        )
        
        return {
            "output": response.answer,
            "sources": [
                {
                    "kb_name": s.kb_name,
                    "doc_name": s.doc_name,
                    "score": s.score,
                }
                for s in response.sources
            ],
            "rewritten_query": response.rewritten_query,
        }
```

## 三、实施步骤

### 阶段1: 快速集成（1-2天）

1. 在 `SupervisorAgent` 中添加 `QueryRewriter`
2. 添加对话历史管理
3. 修改 `_rag_enhanced_chat` 使用重写后的查询

### 阶段2: 完整集成（3-5天）

1. 集成 `MultiTurnRAGManager`
2. 添加上下文压缩
3. 添加引用溯源
4. 添加流式支持

### 阶段3: 优化完善（2-3天）

1. 添加缓存机制
2. 添加性能监控
3. 添加单元测试

## 四、测试用例

```python
# tests/test_query_rewrite_integration.py

import pytest
from app.langchain.agents import SupervisorAgent

@pytest.mark.asyncio
async def test_query_rewrite_integration():
    """测试查询重写集成"""
    agent = SupervisorAgent()
    
    # 第一轮对话
    response1 = await agent.chat("什么是RAG？")
    assert "RAG" in response1["output"]
    
    # 第二轮对话 - 依赖上下文
    response2 = await agent.chat("它的优点是什么？")
    # 应该正确解析"它"为"RAG"
    assert "RAG" in response2["output"] or "检索增强" in response2["output"]
    
    # 验证查询重写
    history = agent._conversation_history
    assert len(history) >= 2

@pytest.mark.asyncio
async def test_pronoun_resolution():
    """测试代词解析"""
    from app.langchain.routers import QueryRewriter, ConversationTurn
    
    rewriter = QueryRewriter()
    
    history = [
        ConversationTurn(role="user", content="介绍一下OpenAI公司"),
        ConversationTurn(role="assistant", content="OpenAI是一家人工智能公司..."),
    ]
    
    result = await rewriter.rewrite("它的产品有哪些？", history)
    
    # "它"应该被解析为"OpenAI"
    assert "OpenAI" in result.rewritten_query
    assert result.confidence > 0.5
```

## 五、配置更新

```python
# backend/app/config.py

class Settings(BaseSettings):
    ...
    
    # 查询重写配置
    QUERY_REWRITE_ENABLED: bool = True
    QUERY_REWRITE_MAX_HISTORY: int = 5
    QUERY_EXPANSION_ENABLED: bool = True
    QUERY_EXPANSION_MAX_VARIATIONS: int = 3
    
    # 多轮RAG配置
    MULTI_TURN_RAG_ENABLED: bool = True
    MULTI_TURN_RAG_MAX_HISTORY_TURNS: int = 10
    MULTI_TURN_RAG_MAX_CONTEXT_TOKENS: int = 4000
```

## 六、预期效果

### 查询重写示例

| 原始查询 | 对话历史 | 重写后查询 |
|----------|----------|------------|
| "它的优点是什么？" | 用户: "什么是RAG？" | "RAG的优点是什么？" |
| "这家公司怎么样？" | 用户: "介绍一下OpenAI" | "OpenAI公司怎么样？" |
| "多少钱？" | 用户: "GPT-4的价格" | "GPT-4的价格是多少？" |

### 查询扩展示例

| 原始查询 | 扩展变体 |
|----------|----------|
| "股票分析" | "股价分析", "股市分析", "证券分析" |
| "技术方案" | "技术解决方案", "技术架构方案" |

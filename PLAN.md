# Self-Bot 测试覆盖完善计划

## 一、现状分析

### 1.1 项目技术栈
- **后端**: FastAPI + LangChain + ChromaDB + SQLAlchemy
- **前端**: React + TypeScript + Zustand + Vite
- **测试框架**: pytest (后端), 无 (前端)

### 1.2 现有问题

| 问题类型 | 具体表现 |
|---------|---------|
| **测试组织混乱** | 49个测试文件散落在根目录，缺乏 `tests/` 目录结构 |
| **缺乏单元测试** | 大多是集成测试和临时调试测试 |
| **前端零测试** | 前端完全没有测试覆盖 |
| **无覆盖率报告** | 没有 pytest-cov 或 jest 覆盖率配置 |
| **无 CI/CD 集成** | 测试未集成到持续集成流程 |

### 1.3 测试文件分类

**需要保留的测试** (tests/ 目录):
- `test_rag_api.py` - RAG API 测试
- `test_agents.py` - Agent 测试
- `test_pdf_parser.py` - PDF 解析器测试
- `test_rag_pipeline.py` - RAG 管道测试

**需要重构的测试** (根目录临时测试):
- `test_api.py`, `test_stream.py` - 需要规范化
- `test_memory.py`, `test_skills.py` - 需要拆分为单元测试
- `test_mcp_*.py` - 需要整合为 MCP 集成测试

**需要删除的测试** (临时调试):
- `test_bcrypt.py`, `test_import.py`, `test_bge.py` 等

---

## 二、测试策略

### 2.1 测试金字塔

```
                    ┌─────────┐
                    │   E2E   │  (端到端测试 - 少量)
                    ├─────────┤
                    │ 集成测试 │  (API + 数据库 - 适量)
                    ├─────────┤
                    │ 单元测试 │  (核心业务逻辑 - 大量)
                    └─────────┘
```

### 2.2 优先级划分

| 优先级 | 模块 | 理由 |
|--------|------|------|
| P0 | 认证系统 | 安全关键 |
| P0 | API 路由层 | 用户交互入口 |
| P1 | 知识库核心 | 核心业务功能 |
| P1 | Agent 系统 | AI 核心逻辑 |
| P2 | MCP 集成 | 外部依赖 |
| P2 | 记忆系统 | 辅助功能 |
| P3 | 前端组件 | UI 层 |

---

## 三、分阶段实施计划

### 阶段一：基础设施搭建 (1-2天)

#### 任务清单
- [ ] 创建 `pytest.ini` 配置文件
- [ ] 配置 `pytest-cov` 覆盖率报告
- [ ] 重组 `tests/` 目录结构
- [ ] 创建测试工具函数和 fixtures
- [ ] 配置前端 Jest + React Testing Library

#### 目录结构
```
backend/
├── tests/
│   ├── conftest.py           # 共享 fixtures
│   ├── unit/                 # 单元测试
│   │   ├── test_auth.py
│   │   ├── test_config.py
│   │   └── test_utils.py
│   ├── integration/          # 集成测试
│   │   ├── test_api.py
│   │   ├── test_knowledge_base.py
│   │   └── test_agents.py
│   └── e2e/                  # 端到端测试
│       └── test_full_pipeline.py
├── pytest.ini
└── requirements.txt          # 添加测试依赖

frontend/
├── src/
│   └── __tests__/            # 测试目录
│       ├── components/
│       ├── pages/
│       └── services/
├── jest.config.js
└── package.json              # 添加测试依赖
```

---

### 阶段二：后端核心单元测试 (3-5天)

#### 2.1 认证系统测试 (P0)
```
tests/unit/test_auth.py
├── test_jwt_token_generation
├── test_jwt_token_validation
├── test_jwt_token_expiration
├── test_password_hashing
├── test_password_verification
└── test_auth_dependencies
```

#### 2.2 配置管理测试 (P0)
```
tests/unit/test_config.py
├── test_default_config_values
├── test_env_override
├── test_config_validation
└── test_invalid_config_handling
```

#### 2.3 API Schema 测试 (P0)
```
tests/unit/test_schemas.py
├── test_chat_request_validation
├── test_chat_response_serialization
├── test_error_response_format
└── test_pagination_schema
```

#### 2.4 知识库核心测试 (P1)
```
tests/unit/knowledge_base/
├── test_parsers.py           # 文档解析器
│   ├── test_pdf_parser
│   ├── test_docx_parser
│   ├── test_excel_parser
│   └── test_markdown_parser
├── test_embedding.py         # 嵌入服务
├── test_bm25.py              # BM25 检索
└── test_search_service.py    # 搜索服务
```

---

### 阶段三：后端集成测试 (3-5天)

#### 3.1 API 端点测试
```
tests/integration/test_api.py
├── test_chat_endpoint
│   ├── test_chat_success
│   ├── test_chat_streaming
│   ├── test_chat_with_tools
│   └── test_chat_error_handling
├── test_auth_endpoints
│   ├── test_login
│   ├── test_register
│   └── test_token_refresh
└── test_knowledge_base_endpoints
    ├── test_create_kb
    ├── test_upload_document
    ├── test_search
    └── test_delete_document
```

#### 3.2 Agent 系统测试
```
tests/integration/test_agents.py
├── test_main_agent_flow
├── test_rag_agent_retrieval
├── test_researcher_agent
├── test_supervisor_agent
└── test_agent_with_tools
```

#### 3.3 记忆系统测试
```
tests/integration/test_memory.py
├── test_short_term_memory
├── test_long_term_memory
├── test_memory_retrieval
└── test_memory_summarization
```

---

### 阶段四：前端测试 (3-5天)

#### 4.1 组件测试
```
src/__tests__/components/
├── ChatInput.test.tsx
│   ├── renders correctly
│   ├── handles input change
│   ├── submits on enter
│   └── handles file upload
├── MessageList.test.tsx
│   ├── renders messages
│   ├── handles streaming message
│   └── scrolls to bottom
├── Sidebar.test.tsx
│   ├── renders navigation
│   └── handles collapse
└── Toast.test.tsx
    ├── shows toast
    └── auto dismisses
```

#### 4.2 页面测试
```
src/__tests__/pages/
├── ChatPage.test.tsx
│   ├── renders chat interface
│   ├── handles message sending
│   └── displays error states
├── KnowledgeBasePage.test.tsx
│   ├── renders kb list
│   ├── handles create kb
│   └── handles delete kb
└── LoginPage.test.tsx
    ├── renders login form
    ├── validates input
    └── handles login success/failure
```

#### 4.3 服务层测试
```
src/__tests__/services/
├── api.test.ts
│   ├── makes correct requests
│   ├── handles errors
│   └── handles streaming
└── knowledgeApi.test.ts
    ├── CRUD operations
    └── search operations
```

---

### 阶段五：E2E 测试 (2-3天)

#### 5.1 关键用户流程
```
tests/e2e/
├── test_user_journey.py
│   ├── test_register_login_flow
│   ├── test_chat_conversation
│   ├── test_knowledge_base_workflow
│   └── test_document_upload_search
└── test_agent_capabilities.py
    ├── test_rag_question_answering
    ├── test_tool_usage
    └── test_skill_execution
```

---

### 阶段六：持续集成 (1天)

#### 6.1 GitHub Actions 配置
```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      - name: Run tests with coverage
        run: |
          cd backend
          pytest --cov=app --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v4

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install dependencies
        run: |
          cd frontend
          npm ci
      - name: Run tests
        run: |
          cd frontend
          npm test -- --coverage
```

---

## 四、测试覆盖率目标

| 阶段 | 后端覆盖率 | 前端覆盖率 |
|------|-----------|-----------|
| 阶段二完成后 | 30% | 0% |
| 阶段三完成后 | 50% | 0% |
| 阶段四完成后 | 50% | 40% |
| 阶段五完成后 | 60% | 50% |
| 最终目标 | 70%+ | 60%+ |

---

## 五、测试最佳实践

### 5.1 命名规范
```python
# 测试文件: test_<module>.py
# 测试类: Test<Feature>
# 测试方法: test_<scenario>_<expected_result>

class TestAuthToken:
    def test_create_token_success(self):
        ...
    
    def test_create_token_expired_raises_error(self):
        ...
```

### 5.2 AAA 模式
```python
def test_user_login_success():
    # Arrange
    user = create_test_user()
    credentials = {"username": "test", "password": "pass"}
    
    # Act
    response = client.post("/api/auth/login", json=credentials)
    
    # Assert
    assert response.status_code == 200
    assert "access_token" in response.json()
```

### 5.3 Fixtures 复用
```python
# conftest.py
@pytest.fixture
def test_user():
    return {"username": "testuser", "password": "testpass"}

@pytest.fixture
def auth_headers(test_user):
    token = create_token(test_user)
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def client():
    return TestClient(app)
```

---

## 六、执行建议

### 6.1 每日任务分配建议

| 日期 | 任务 | 预计产出 |
|------|------|---------|
| Day 1 | 基础设施搭建 | pytest.ini, conftest.py, 目录结构 |
| Day 2-3 | 认证+配置单元测试 | 20+ 测试用例 |
| Day 4-5 | 知识库单元测试 | 30+ 测试用例 |
| Day 6-7 | API 集成测试 | 25+ 测试用例 |
| Day 8-9 | Agent 集成测试 | 15+ 测试用例 |
| Day 10-12 | 前端组件测试 | 30+ 测试用例 |
| Day 13-14 | 前端页面+服务测试 | 20+ 测试用例 |
| Day 15 | E2E 测试 | 10+ 测试用例 |
| Day 16 | CI/CD 配置 | GitHub Actions |

### 6.2 快速启动命令

```bash
# 后端测试
cd backend
pytest                           # 运行所有测试
pytest tests/unit               # 只运行单元测试
pytest --cov=app --cov-report=html  # 生成覆盖率报告

# 前端测试
cd frontend
npm test                        # 运行所有测试
npm test -- --coverage          # 生成覆盖率报告
npm test -- --watch             # 监听模式
```

---

## 七、风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| 外部 API 依赖 | 测试不稳定 | Mock 外部服务 |
| 数据库状态 | 测试污染 | 使用测试数据库，每次测试后清理 |
| 异步代码 | 测试复杂 | 使用 pytest-asyncio |
| LLM 调用成本 | 成本高 | Mock LLM 响应 |

---

## 八、下一步行动

1. **确认计划** - 用户审阅并确认计划
2. **开始阶段一** - 搭建测试基础设施
3. **逐步推进** - 按优先级逐步添加测试
4. **持续监控** - 每周检查覆盖率报告

请确认此计划后，我将开始执行阶段一的任务。

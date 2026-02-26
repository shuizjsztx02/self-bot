# Self-Bot RAG 功能改进计划

---

## 计划概览

```
阶段划分：
┌─────────────────────────────────────────────────────────────────────────────────┐
│  阶段一：关键缺陷修复 (P0)                                                        │
│  预计工期：1-2 天                                                                │
│  目标：修复影响核心功能的缺陷                                                     │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────────┐
│  阶段二：用户体验优化 (P1)                                                        │
│  预计工期：2-3 天                                                                │
│  目标：完善前端交互，提升易用性                                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────────┐
│  阶段三：高级功能集成 (P2)                                                        │
│  预计工期：3-5 天                                                                │
│  目标：集成查询增强、权限管理等高级功能                                           │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────────┐
│  阶段四：系统完善 (P3)                                                           │
│  预计工期：2-3 天                                                                │
│  目标：用户组管理、操作日志、审计功能                                             │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 阶段一：关键缺陷修复 (P0)

**预计工期**：1-2 天

**目标**：修复影响核心功能的缺陷，确保基础功能可用

### 任务清单

| 任务ID | 任务名称 | 具体内容 | 产出物 | 验证方式 |
|--------|----------|----------|--------|----------|
| P0-1 | 修复权限撤销参数不匹配 | 前端 `revokePermission` 改为传递 `permission_id` | `knowledgeApi.ts` 修改 | 权限撤销功能测试 |
| P0-2 | 添加文档更新 API | 后端实现 `PUT /documents/{doc_id}`，支持修改元数据 | `documents.py` 路由更新 | API 文档验证 |
| P0-3 | 添加文档重新处理 API | 后端实现 `POST /documents/{doc_id}/reprocess` | 新增路由 | 失败文档重试测试 |
| P0-4 | 配置 BM25 索引持久化 | 在 `SearchService` 中配置 `persist_path` | `search.py` 配置更新 | 重启后搜索测试 |
| P0-5 | 修复前端类型定义 | 补充 `KBPermission` 缺失字段 | `knowledge.ts` 类型更新 | TypeScript 编译通过 |

### 详细说明

#### P0-1：修复权限撤销参数不匹配

**问题**：
```typescript
// 前端当前代码
revokePermission: async (kbId: string, userId: string): Promise<void> => {
  await api.delete(`/knowledge-bases/${kbId}/permissions/${userId}`)
}
```

**修复方案**：
```typescript
// 修改为
revokePermission: async (kbId: string, permissionId: string): Promise<void> => {
  await api.delete(`/knowledge-bases/${kbId}/permissions/${permissionId}`)
}
```

**验证**：
1. 调用 `GET /knowledge-bases/{id}/permissions` 获取权限列表
2. 调用 `DELETE /knowledge-bases/{id}/permissions/{permission_id}` 删除权限
3. 再次获取权限列表确认删除成功

---

#### P0-2：添加文档更新 API

**后端实现**：
```python
@router.put("/{doc_id}", response_model=DocumentResponse)
async def update_document(
    doc_id: str,
    data: DocumentUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    # 实现文档元数据更新
    pass
```

**Schema 定义**：
```python
class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[List[str]] = None
    folder_id: Optional[str] = None
```

**验证**：
1. 上传文档
2. 调用 `PUT /documents/{doc_id}` 修改标题和标签
3. 调用 `GET /documents/{doc_id}` 确认修改成功

---

#### P0-3：添加文档重新处理 API

**后端实现**：
```python
@router.post("/{doc_id}/reprocess")
async def reprocess_document(
    doc_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    # 重置文档状态为 pending
    # 触发后台处理任务
    pass
```

**验证**：
1. 上传一个会处理失败的文档（如损坏的 PDF）
2. 调用 `POST /documents/{doc_id}/reprocess`
3. 观察文档状态变化

---

#### P0-4：配置 BM25 索引持久化

**修改位置**：`app/knowledge_base/services/search.py`

```python
from app.knowledge_base.dependencies import get_bm25_index

class SearchService:
    def __init__(self, db: AsyncSession, persist_path: str = "data/bm25_indexes"):
        self.db = db
        self.persist_path = persist_path
    
    async def _get_bm25_index(self, kb_id: str) -> BM25Index:
        return get_bm25_index(kb_id, self.persist_path)
```

**验证**：
1. 上传文档并搜索
2. 重启后端服务
3. 再次搜索确认 BM25 结果正常

---

### 阶段一验收标准

- [ ] 权限撤销功能正常工作
- [ ] 文档元数据可修改
- [ ] 文档可重新处理
- [ ] BM25 索引重启后保留
- [ ] TypeScript 编译无错误

---

## 阶段二：用户体验优化 (P1)

**预计工期**：2-3 天

**目标**：完善前端交互，提升易用性

### 任务清单

| 任务ID | 任务名称 | 具体内容 | 产出物 | 验证方式 |
|--------|----------|----------|--------|----------|
| P1-1 | 实现知识库列表分页 | 添加分页组件和逻辑 | `KnowledgeBasePage.tsx` 更新 | 大量数据测试 |
| P1-2 | 实现文档列表分页 | 添加分页组件和逻辑 | `KnowledgeBaseDetailPage.tsx` 更新 | 大量数据测试 |
| P1-3 | 添加文档预览功能 | 文档详情弹窗 + 分块展示 | `DocumentPreview.tsx` 新组件 | 预览测试 |
| P1-4 | 实现知识库设置页面 | 配置修改 + 权限管理 | `KnowledgeBaseSettings.tsx` 新页面 | 设置保存测试 |
| P1-5 | 添加批量操作 | 批量选择 + 批量删除 | 批量操作 UI | 批量删除测试 |
| P1-6 | 添加搜索结果分页 | 支持"加载更多"或分页 | `SearchPage.tsx` 更新 | 搜索测试 |

### 详细说明

#### P1-1 & P1-2：分页实现

**后端已有分页参数**：
- `skip`: 偏移量
- `limit`: 每页数量

**前端实现**：
```typescript
interface PaginationState {
  page: number
  pageSize: number
  total: number
}

// 分页组件
<Pagination
  current={page}
  pageSize={pageSize}
  total={total}
  onChange={(p, ps) => { setPage(p); setPageSize(ps); }}
/>
```

---

#### P1-3：文档预览功能

**组件设计**：
```typescript
interface DocumentPreviewProps {
  documentId: string
  open: boolean
  onClose: () => void
}

// 功能：
// 1. 显示文档基本信息
// 2. 显示分块列表
// 3. 高亮搜索命中位置
// 4. 复制分块内容
```

**后端支持**：
- `GET /documents/{doc_id}` - 文档详情
- `GET /documents/{doc_id}/chunks` - 分块列表

---

#### P1-4：知识库设置页面

**功能模块**：
1. 基本信息设置（名称、描述）
2. 嵌入模型配置（embedding_model）
3. 分块参数配置（chunk_size, chunk_overlap）
4. 权限管理（用户列表、角色分配）
5. 危险操作（删除知识库）

---

#### P1-5：批量操作

**UI 设计**：
- 列表项添加复选框
- 底部显示已选数量
- 批量操作按钮（删除、移动）

**后端 API**：
```python
@router.post("/batch-delete")
async def batch_delete_documents(doc_ids: List[str], ...):
    pass

@router.post("/batch-move")
async def batch_move_documents(doc_ids: List[str], folder_id: str, ...):
    pass
```

---

### 阶段二验收标准

- [ ] 知识库列表支持分页
- [ ] 文档列表支持分页
- [ ] 可预览文档内容和分块
- [ ] 可修改知识库配置
- [ ] 可批量删除文档
- [ ] 搜索结果支持分页

---

## 阶段三：高级功能集成 (P2)

**预计工期**：3-5 天

**目标**：集成查询增强、权限管理等高级功能

### 任务清单

| 任务ID | 任务名称 | 具体内容 | 产出物 | 验证方式 |
|--------|----------|----------|--------|----------|
| P2-1 | 集成查询重写功能 | 前端调用 QueryRewriter | 搜索增强 UI | 查询重写测试 |
| P2-2 | 实现权限管理 UI | 权限列表 + 授权/撤销 | `PermissionManager.tsx` | 权限操作测试 |
| P2-3 | 添加文档下载功能 | 后端下载 API + 前端按钮 | 下载功能 | 文件下载测试 |
| P2-4 | 实现搜索历史 | 本地存储搜索记录 | 搜索历史组件 | 历史记录测试 |
| P2-5 | 集成引用溯源 | 显示来源和置信度 | `CitationDisplay.tsx` | 引用展示测试 |
| P2-6 | 添加相似文档推荐 | "查找相似"功能 | 相似文档 API | 相似推荐测试 |

### 详细说明

#### P2-1：集成查询重写功能

**后端已有**：`QueryRewriter` 类

**前端集成**：
```typescript
// 搜索选项
interface SearchOptions {
  useQueryRewrite: boolean  // 启用查询重写
  useHybridSearch: boolean  // 启用混合检索
  useRerank: boolean        // 启用重排序
}

// 显示重写后的查询
<SearchResult>
  <OriginalQuery>原始查询</OriginalQuery>
  <RewrittenQuery>重写后查询</RewrittenQuery>
  <Results>搜索结果</Results>
</SearchResult>
```

---

#### P2-2：权限管理 UI

**组件设计**：
```typescript
interface PermissionManagerProps {
  kbId: string
}

// 功能：
// 1. 显示当前权限列表
// 2. 添加用户权限（用户选择 + 角色选择）
// 3. 撤销用户权限
// 4. 显示权限到期时间
```

---

#### P2-3：文档下载功能

**后端 API**：
```python
@router.get("/{doc_id}/download")
async def download_document(
    doc_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    # 返回文件流
    pass
```

**前端调用**：
```typescript
downloadDocument: async (docId: string): Promise<Blob> => {
  const response = await api.get(`/documents/${docId}/download`, {
    responseType: 'blob'
  })
  return response.data
}
```

---

#### P2-5：引用溯源

**后端已有**：`SourceAttribution` 类

**前端展示**：
```typescript
interface SearchResultWithCitation {
  content: string
  score: number
  source: {
    docName: string
    pageNumber?: number
    sectionTitle?: string
  }
  confidence: number  // 置信度 0-1
  citation: string    // 引用文本
}
```

---

### 阶段三验收标准

- [ ] 查询重写功能可用
- [ ] 权限管理 UI 完整
- [ ] 文档可下载
- [ ] 搜索历史可查看
- [ ] 搜索结果显示引用
- [ ] 相似文档可推荐

---

## 阶段四：系统完善 (P3)

**预计工期**：2-3 天

**目标**：用户组管理、操作日志、审计功能

### 任务清单

| 任务ID | 任务名称 | 具体内容 | 产出物 | 验证方式 |
|--------|----------|----------|--------|----------|
| P3-1 | 用户组管理 API | CRUD 接口 | `user_groups.py` 路由 | API 测试 |
| P3-2 | 用户组管理 UI | 组列表 + 成员管理 | `UserGroupManager.tsx` | 组操作测试 |
| P3-3 | 操作日志 API | 日志查询接口 | `operation_logs.py` 路由 | 日志查询测试 |
| P3-4 | 操作日志 UI | 日志列表 + 筛选 | `OperationLogPage.tsx` | 日志展示测试 |
| P3-5 | 属性规则 API | 自动权限规则 | `attribute_rules.py` 路由 | 规则测试 |
| P3-6 | 文件夹权限继承 | 实现继承逻辑 | 权限服务更新 | 继承测试 |

### 详细说明

#### P3-1：用户组管理 API

**路由设计**：
```python
# 用户组
POST   /user-groups              # 创建用户组
GET    /user-groups              # 列出用户组
GET    /user-groups/{id}         # 获取用户组
PUT    /user-groups/{id}         # 更新用户组
DELETE /user-groups/{id}         # 删除用户组

# 成员管理
POST   /user-groups/{id}/members     # 添加成员
DELETE /user-groups/{id}/members/{uid}  # 移除成员
```

---

#### P3-3：操作日志 API

**路由设计**：
```python
GET /operation-logs  # 查询日志
    ?user_id=xxx
    &action=create|update|delete
    &resource_type=knowledge_base|document|folder
    &start_date=2024-01-01
    &end_date=2024-12-31
```

---

#### P3-5：属性规则 API

**用途**：根据用户属性自动分配权限

```python
POST /knowledge-bases/{kb_id}/attribute-rules
{
  "attribute_type": "department",
  "operator": "==",
  "user_attribute": "department",
  "resource_attribute": "department",
  "role": "viewer"
}

# 规则：如果用户部门 == 知识库部门，自动获得 viewer 权限
```

---

### 阶段四验收标准

- [ ] 用户组可创建和管理
- [ ] 组权限可授权
- [ ] 操作日志可查询
- [ ] 属性规则可配置
- [ ] 文件夹权限可继承

---

## 测试计划

### 每阶段测试流程

```
1. 单元测试
   - 后端 API 单元测试
   - 前端组件测试

2. 集成测试
   - API 端到端测试
   - 前后端联调测试

3. 功能测试
   - 用户场景测试
   - 边界条件测试

4. 回归测试
   - 确保新功能不影响现有功能
```

### 测试用例模板

```markdown
## 测试用例：[功能名称]

### 前置条件
- 已登录用户
- 已创建测试知识库

### 测试步骤
1. 步骤一
2. 步骤二
3. 步骤三

### 预期结果
- 结果一
- 结果二

### 实际结果
- [ ] 通过
- [ ] 失败（原因：xxx）
```

---

## 风险评估

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 后端 API 变更影响前端 | 中 | 高 | 保持 API 向后兼容 |
| BM25 持久化性能问题 | 低 | 中 | 异步保存，批量写入 |
| 权限逻辑复杂度 | 中 | 高 | 充分测试，编写文档 |
| 大数据量分页性能 | 中 | 中 | 添加索引，优化查询 |

---

## 附录：API 完整清单

### 已实现 API

| 模块 | 数量 | 状态 |
|------|------|------|
| 知识库管理 | 6 | ✅ |
| 文件夹管理 | 4 | ✅ |
| 权限管理 | 3 | ⚠️ |
| 文档管理 | 5 | ⚠️ |
| 搜索功能 | 2 | ✅ |
| 认证功能 | 5 | ✅ |

### 待实现 API

| API | 优先级 | 阶段 |
|-----|--------|------|
| PUT /documents/{id} | P0 | 阶段一 |
| POST /documents/{id}/reprocess | P0 | 阶段一 |
| POST /documents/batch-delete | P1 | 阶段二 |
| POST /documents/batch-move | P1 | 阶段二 |
| GET /documents/{id}/download | P2 | 阶段三 |
| POST /search/similar | P2 | 阶段三 |
| 用户组 CRUD | P3 | 阶段四 |
| 操作日志查询 | P3 | 阶段四 |
| 属性规则 CRUD | P3 | 阶段四 |

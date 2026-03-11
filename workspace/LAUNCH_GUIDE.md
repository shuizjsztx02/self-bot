# 🚀 ClawHub 完整链路测试启动指南

## 快速启动

### 终端 1 - 启动后端

```bash
cd backend
python main.py
```

预期日志：
```
INFO: Uvicorn running on http://127.0.0.1:8000
[ChatService] 创建并注册全局 SkillManager 单例
```

### 终端 2 - 启动前端

```bash
cd frontend
npm run dev
```

预期日志：
```
VITE v5.1.0  ready in XXX ms

➜  Local:   http://localhost:5173/
```

### 浏览器

访问：`http://localhost:5173`

---

## 测试 Query（复制粘贴）

输入以下内容到聊天框：

```
帮我在 Notion 工作区创建一个项目管理系统，需要能查询数据库和创建新的任务页面
```

---

## 完整链路日志验证

### 步骤 1️⃣ - 本地技能匹配失败

**后端日志**：
```
[SkillMatcher] 本地无匹配，搜索 ClawHub: 帮我在 Notion 工作区创建一个...
```

✅ **说明**：本地没有匹配的技能，触发ClawHub降级

---

### 步骤 2️⃣ - ClawHub 搜索

**后端日志**：
```
[ClawHub] 搜索返回 1 个结果: notion (置信度: 0.7+)
```

✅ **说明**：在ClawHub找到了Notion技能

---

### 步骤 3️⃣ - 自动安装技能

**后端日志**：
```
[SkillMatcher] 自动安装 ClawHub 技能: notion (置信度: 0.75)
[ClawHub] Mock 技能安装成功: notion -> ./skills/installed/notion/SKILL.md
```

✅ **说明**：技能SKILL.md已下载并保存

---

### 步骤 4️⃣ - 依赖检测

**后端日志**：
```
[DependencyResolver] Notion Integration: pip: notion-client>=2.0.0; mcp: notion; env: NOTION_API_KEY
[SkillMatcher] 技能已下载但依赖不满足: pip: notion-client>=2.0.0; mcp: notion; env: NOTION_API_KEY
```

✅ **说明**：检测到缺失3个依赖项

---

### 步骤 5️⃣ - 前端收到确认事件

**浏览器**：弹出蓝色对话框

```
技能 Notion Integration 需要安装以下依赖才能正常使用，是否继续？

☑ Python 包
  - notion-client>=2.0.0

☑ MCP 服务
  - notion

☐ 环境变量（需手动填写）
  - NOTION_API_KEY: [输入框]

[跳过] [确认安装]
```

✅ **说明**：用户可以选择性安装或填写环境变量

---

### 步骤 6️⃣ - 用户确认（前端操作）

1. 在 `NOTION_API_KEY` 输入框中输入任意值（例如：`test_key_123`）
2. 点击 **确认安装** 按钮

**前端日志**：
```
POST /api/skills/confirm-install
```

---

### 步骤 7️⃣ - 依赖自动安装

**后端日志**：
```
[API] POST /api/skills/confirm-install: skill_slug=notion
[Installer] 安装中... pip install notion-client>=2.0.0
[Installer] pip installed: ['notion-client>=2.0.0']
[Installer] Registering MCP server: notion
[Installer] MCP server registered: notion
```

✅ **说明**：依赖自动安装中，显示进度

---

### 步骤 8️⃣ - 安装完成

**浏览器**：对话框自动关闭，聊天区显示：

```
Notion Integration: 所有依赖已安装，技能已就绪。
```

**后端日志**：
```
[Installer] 安装完成！所有依赖已成功安装
```

✅ **说明**：完整链路测试成功！

---

## 快速检查清单

| ✅ | 检查项 | 日志位置 |
|----|--------|--------|
| ☐ | 本地匹配失败 | 后端 `[SkillMatcher] 本地无匹配` |
| ☐ | ClawHub 搜索成功 | 后端 `[ClawHub] 搜索返回` |
| ☐ | 技能安装成功 | 后端 `[ClawHub] Mock 技能安装成功` |
| ☐ | 依赖检测执行 | 后端 `[DependencyResolver]` |
| ☐ | SSE 事件发送 | 后端 `skill_dependency_confirm` |
| ☐ | 对话框弹出 | 浏览器可见 |
| ☐ | 用户确认 | 后端 `POST /api/skills/confirm-install` |
| ☐ | 依赖安装执行 | 后端 `[Installer] pip installed` |
| ☐ | 完成通知发送 | 后端 `skill_ready` |
| ☐ | 对话框关闭 | 浏览器隐藏 |

---

## 常见问题

### Q: 对话框没有出现？
**A**: 检查浏览器控制台（F12）是否有错误，或查看后端日志是否有异常

### Q: 后端报错 `'list' object has no attribute 'name'`？
**A**: 已在 Bug 修复中解决，请确保使用最新代码

### Q: 如何跳过手动输入环境变量？
**A**: 在启动后端前，预设环境变量：
```bash
# Linux/Mac
export NOTION_API_KEY="test_key_123"

# Windows PowerShell
$env:NOTION_API_KEY="test_key_123"

# 然后启动
python main.py
```

### Q: 想测试其他技能？
**A**: 使用这些 query 之一：
- `我想制作一个PowerPoint演示文稿` → pptx
- `帮我处理Excel表格数据` → xlsx
- `集成GitHub自动化代码审查` → github

---

## 故障排查

### 情况 1：后端无法启动
```bash
cd backend
pip install -r requirements.txt
python main.py
```

### 情况 2：前端无法启动
```bash
cd frontend
npm install
npm run dev
```

### 情况 3：连接错误
- 确保后端运行在 `http://127.0.0.1:8000`
- 确保前端运行在 `http://localhost:5173`
- 检查防火墙设置

---

## 日志输出位置

**后端**：
```
- 终端标准输出
- logs/ 目录（如配置）
```

**前端**：
- 浏览器控制台 (F12)
- 终端标准输出

---

祝测试顺利！🎉

# Self-Bot

一个基于 LangChain 的智能个人助理 Agent，支持多模态文档处理、知识库管理和 MCP 工具扩展。

## ✨ 特性

- 🤖 **多模型支持** - OpenAI、Anthropic、本地模型等
- 📄 **文档处理** - Word/Excel/PPT/PDF 创建、编辑、转换
- 🔍 **RAG 知识库** - 向量检索、智能问答
- 🛠️ **MCP 工具生态** - 139+ 内置工具，支持自定义扩展
- 💬 **流式对话** - 实时响应，支持中断
- 🎯 **技能系统** - 可插拔的技能模块

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- pnpm / npm

### 安装

```bash
# 克隆项目
git clone https://github.com/your-username/self-bot.git
cd self-bot

# 后端安装
cd backend
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 配置 API Keys

# 前端安装
cd ../frontend
npm install
```

### 启动

```bash
# 启动后端 (端口 8001)
cd backend
python run.py --port 8001

# 启动前端 (端口 3000)
cd frontend
npm run dev
```

访问 http://localhost:3000 开始使用。

## 📁 项目结构

```
self-bot/
├── backend/
│   ├── app/
│   │   ├── api/          # API 路由
│   │   ├── auth/         # 认证模块
│   │   ├── langchain/    # Agent 核心
│   │   ├── mcp/          # MCP 工具集成
│   │   ├── knowledge_base/ # 知识库
│   │   └── skills/       # 技能模块
│   ├── mcp_servers/      # MCP 服务器
│   │   ├── word/         # Word 文档工具
│   │   ├── excel/        # Excel 工具
│   │   ├── pptx/         # PPT 工具
│   │   ├── notion/       # Notion 集成
│   │   └── feishu/       # 飞书集成
│   └── workspace/        # 工作目录
├── frontend/             # React 前端
└── README.md
```

## ⚙️ 配置

编辑 `backend/.env`：

```env
# LLM Provider
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-xxx

# MCP 预加载
PRELOAD_MCP_TOOLS=true

# Notion (可选)
NOTION_API_KEY=ntn_xxx
NOTION_DATABASE_ID=xxx

# 飞书 (可选)
FEISHU_APP_ID=xxx
FEISHU_APP_SECRET=xxx
```

## 🛠️ MCP 工具

| 服务 | 工具数 | 功能 |
|------|--------|------|
| Word | 54 | 文档创建、编辑、PDF转换 |
| Excel | 25 | 表格操作、数据处理 |
| PPTX | 37 | 幻灯片创建、设计 |
| Notion | 4 | 笔记管理 |
| Feishu | 19 | 飞书文档、多维表格 |

## 📖 使用示例

```
用户: 创建一份项目报告 Word 文档，包含标题和三个段落
Agent: [调用 create_document, add_paragraph] 已创建 report.docx

用户: 将文档转换为 PDF
Agent: [调用 convert_to_pdf] 已生成 report.pdf

用户: 搜索知识库中关于机器学习的内容
Agent: [调用 RAG 检索] 找到 5 篇相关文档...
```

## 🔧 开发

```bash
# 运行测试
cd backend
pytest

# 代码检查
ruff check app/

# 类型检查
pyright app/
```

## 📄 License

MIT License

## 🤝 贡献

欢迎 Issue 和 Pull Request！

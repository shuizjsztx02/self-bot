import os
import sys
import asyncio
import logging

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)

logger = logging.getLogger(__name__)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.db import init_db
from app.api import router
from app.knowledge_base.routes import (
    kb_router, 
    auth_router, 
    documents_router, 
    search_router, 
    user_groups_router,
    operation_logs_router,
    attribute_rules_router,
)


def setup_langsmith():
    if settings.LANGSMITH_API_KEY:
        os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
        os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT or "self-bot"
        os.environ["LANGSMITH_TRACING"] = str(settings.LANGSMITH_TRACING).lower()
        print(f"✅ LangSmith enabled: project={settings.LANGSMITH_PROJECT}")
    else:
        print("⚠️ LangSmith not configured (LANGSMITH_API_KEY not set)")


async def preload_mcp_tools():
    """预加载 MCP 工具"""
    print("\n" + "=" * 50)
    print("预加载 MCP 工具...")
    print("=" * 50)
    
    try:
        from app.mcp import get_all_mcp_tools
        tools = await get_all_mcp_tools()
        print(f"✅ 成功预加载 {len(tools)} 个 MCP 工具")
    except Exception as e:
        print(f"⚠️ MCP 工具预加载失败: {e}")
    
    print("=" * 50 + "\n")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    
    if settings.PRELOAD_MCP_TOOLS:
        await preload_mcp_tools()
    else:
        print("\n" + "=" * 50)
        print("⚠️ MCP 工具预加载已禁用 (PRELOAD_MCP_TOOLS=False)")
        print("   如需启用，请在 .env 中设置 PRELOAD_MCP_TOOLS=true")
        print("=" * 50 + "\n")
    
    yield


app = FastAPI(
    title="Self-Bot API",
    description="AI Agent with MCP Tools, Memory and Skills",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(kb_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(user_groups_router, prefix="/api")
app.include_router(operation_logs_router, prefix="/api")
app.include_router(attribute_rules_router, prefix="/api")

setup_langsmith()


@app.get("/")
async def root():
    return {
        "name": "Self-Bot API",
        "version": "1.0.0",
        "docs": "/docs",
    }

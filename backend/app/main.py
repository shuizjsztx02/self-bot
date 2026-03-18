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

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.orm").setLevel(logging.WARNING)

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
    users_router,
)
from app.core.device_utils import log_device_status


def setup_langsmith():
    if settings.LANGSMITH_API_KEY:
        os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
        os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT or "self-bot"
        os.environ["LANGSMITH_TRACING"] = str(settings.LANGSMITH_TRACING).lower()
        print(f"✅ LangSmith enabled: project={settings.LANGSMITH_PROJECT}")
    else:
        print("⚠️ LangSmith not configured (LANGSMITH_API_KEY not set)")


async def preload_mcp_tools():
    """通过 Registry 预加载所有 MCP 工具（触发每个 MCP lazy loader）"""
    print("\n" + "=" * 50)
    print("预加载 MCP 工具（通过 Registry）...")
    print("=" * 50)

    try:
        from app.langchain.tools.registry import get_registry
        from app.langchain.tools.metadata import ToolSource

        registry = get_registry()
        mcp_names = registry.get_by_source(ToolSource.MCP)
        tools = await registry.get_tools_async(names=mcp_names, load_lazy=True)
        print(f"✅ 成功预加载 {len(tools)} 个 MCP 工具")
    except Exception as e:
        print(f"⚠️ MCP 工具预加载失败: {e}")

    print("=" * 50 + "\n")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_device_status()

    await init_db()
    
    # 初始化 HTTP 客户端管理器
    print("\n" + "=" * 50)
    print("初始化 HTTP 客户端管理器...")
    print("=" * 50)
    try:
        from app.core.http_client import HTTPClientManager
        await HTTPClientManager.get_instance()
        print("✅ HTTP Client Manager initialized")
    except Exception as e:
        print(f"⚠️ HTTP 客户端管理器初始化失败: {e}")
    print("=" * 50 + "\n")

    # 初始化工具注册中心（本地工具 + MCP 懒加载器注册）
    print("\n" + "=" * 50)
    print("初始化工具注册中心...")
    print("=" * 50)
    try:
        from app.langchain.tools import initialize_tools
        await initialize_tools()
        print("✅ 工具注册中心初始化完成")
    except Exception as e:
        print(f"⚠️ 工具注册中心初始化失败: {e}")
    print("=" * 50 + "\n")

    if settings.PRELOAD_MCP_TOOLS:
        await preload_mcp_tools()
    else:
        print("\n" + "=" * 50)
        print("⚠️ MCP 工具预加载已禁用 (PRELOAD_MCP_TOOLS=False)，将在首次使用时懒加载")
        print("   如需启用，请在 .env 中设置 PRELOAD_MCP_TOOLS=true")
        print("=" * 50 + "\n")
    
    # 🆕 自进化系统集成：启动EvolutionMonitor
    from app.evolution import get_evolution_monitor, evolution_settings
    
    if evolution_settings.EVOLUTION_ENABLED:
        print("\n" + "=" * 50)
        print("启动自进化系统...")
        print("=" * 50)
        
        monitor = get_evolution_monitor()
        await monitor.start()
        
        print("✅ 自进化系统已启动")
        print(f"   - 检查间隔: {evolution_settings.EVOLUTION_CHECK_INTERVAL_HOURS}小时")
        print(f"   - 分析天数: {evolution_settings.EVOLUTION_ANALYSIS_DAYS}天")
        print("=" * 50 + "\n")
    else:
        print("\n" + "=" * 50)
        print("⚠️ 自进化系统已禁用 (EVOLUTION_ENABLED=False)")
        print("   如需启用，请在 .env 中设置 EVOLUTION_ENABLED=true")
        print("=" * 50 + "\n")
    
    yield
    
    print("\n" + "=" * 50)
    print("关闭服务...")
    print("=" * 50)
    
    # 关闭 HTTP 客户端管理器
    try:
        from app.core.http_client import HTTPClientManager
        await HTTPClientManager.close()
        print("✅ HTTP Client Manager closed")
    except Exception as e:
        print(f"⚠️ HTTP 客户端管理器关闭失败: {e}")
    
    try:
        from app.core.managers import get_global_managers
        managers = get_global_managers()
        await managers.cleanup_all()
        print("✅ MCP 工具已清理")
    except Exception as e:
        print(f"⚠️ MCP 清理失败: {e}")
    
    try:
        from app.langchain.graph.checkpointer import get_checkpointer_manager
        checkpointer = get_checkpointer_manager()
        await checkpointer.close()
        print("✅ Checkpointer 已关闭")
    except Exception as e:
        print(f"⚠️ Checkpointer 清理失败: {e}")
    
    if evolution_settings.EVOLUTION_ENABLED:
        print("\n" + "=" * 50)
        print("关闭自进化系统...")
        print("=" * 50)
        
        monitor = get_evolution_monitor()
        await monitor.stop()
        
        print("✅ 自进化系统已关闭")
        print("=" * 50 + "\n")


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
app.include_router(users_router, prefix="/api")

setup_langsmith()


@app.get("/")
async def root():
    return {
        "name": "Self-Bot API",
        "version": "1.0.0",
        "docs": "/docs",
    }

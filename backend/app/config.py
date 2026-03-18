from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    ENV: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/database/selfbot.db"
    
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o"
    
    ANTHROPIC_API_KEY: Optional[str] = None
    CLAUDE_MODEL: str = "claude-3-5-sonnet-20241022"
    
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    
    QWEN_API_KEY: Optional[str] = None
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen-plus"
    
    GLM_API_KEY: Optional[str] = None
    GLM_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    GLM_MODEL: str = "glm-4-plus"
    
    MINIMAX_API_KEY: Optional[str] = None
    MINIMAX_GROUP_ID: Optional[str] = None
    MINIMAX_BASE_URL: str = "https://api.minimax.chat/v1"
    MINIMAX_MODEL: str = "abab6.5s-chat"
    
    MOONSHOT_API_KEY: Optional[str] = None
    MOONSHOT_BASE_URL: str = "https://api.moonshot.cn/v1"
    MOONSHOT_MODEL: str = "moonshot-v1-8k"
    
    TAVILY_API_KEY: Optional[str] = None
    PERPLEXITY_API_KEY: Optional[str] = None
    SERPAPI_API_KEY: Optional[str] = None
    
    DEFAULT_LLM_PROVIDER: str = "openai"
    
    WORKSPACE_PATH: str = "./workspace"
    
    FILE_ACCESS_ALLOWED_DIRS: list = ["./workspace"]
    FILE_ACCESS_DENIED_DIRS: list = []
    FILE_ACCESS_STRICT_MODE: bool = True
    
    # 知识库存储路径
    KB_DOCUMENT_PATH: str = "./data/knowledge_base/documents"
    KB_VECTOR_PATH: str = "./data/knowledge_base/vectors"
    KB_INDEX_PATH: str = "./data/knowledge_base/indexes"
    
    # Agent存储路径
    AGENT_MEMORY_PATH: str = "./data/agent/memories"
    AGENT_VECTOR_PATH: str = "./data/agent/vectors"
    AGENT_TRACE_PATH: str = "./data/agent/traces"
    
    # Agent记忆配置
    MEMORY_MAX_TOKENS: int = 10000
    MEMORY_SUMMARY_THRESHOLD: float = 0.8
    MEMORY_KEEP_RECENT: int = 5
    
    # Agent实例缓存配置
    AGENT_CACHE_TTL: int = 3600
    AGENT_CACHE_MAX_SIZE: int = 100
    
    # 历史消息加载配置
    HISTORY_LOAD_ENABLED: bool = True
    HISTORY_LOAD_LIMIT: int = 20
    HISTORY_MAX_TOKENS: int = 4000
    
    # 记忆追踪配置
    MEMORY_TRACE_ENABLED: bool = True
    MEMORY_TRACE_CONTENT_PREVIEW: int = 100
    MEMORY_TRACE_LOG_LEVEL: str = "INFO"
    
    EMBEDDING_MODEL: str = "BAAI/bge-base-zh-v1.5"
    RERANKER_MODEL: str = "BAAI/bge-reranker-base"
    MODEL_HUB_PATH: str = "./model_hub"
    
    MODEL_DEVICE: str = "auto"
    MODEL_FORCE_CPU: bool = False
    
    LANGSMITH_API_KEY: Optional[str] = None
    LANGSMITH_PROJECT: str = "self-bot"
    LANGSMITH_TRACING: bool = False
    
    MCP_SERVER_NAME: str = "self-bot"
    MCP_SERVER_VERSION: str = "1.0.0"
    
    PRELOAD_MCP_TOOLS: bool = False
    
    AGENT_MAX_ITERATIONS: int = 150
    RESEARCHER_MAX_ITERATIONS: int = 80
    
    LANGGRAPH_CHECKPOINT_ENABLED: bool = True
    LANGGRAPH_CHECKPOINT_DB_PATH: str = "./data/database/checkpoint.db"
    LANGGRAPH_CHECKPOINT_TTL_HOURS: int = 24
    LANGGRAPH_CHECKPOINT_MAX_HISTORY: int = 100
    
    TOOL_SELECTION_MAX_TOOLS: int = 50

    # MCP 服务器配置（config-driven，initializer 从此处读取）
    MCP_SERVERS: dict = {
        "word":   {"category": "office_word",  "tags": ["office", "word", "document"]},
        "excel":  {"category": "office_excel", "tags": ["office", "excel", "spreadsheet"]},
        "pptx":   {"category": "office_pptx", "tags": ["office", "pptx", "presentation"]},
        "notion": {"category": "notion",       "tags": ["notion", "notes"]},
        "feishu": {"category": "feishu",       "tags": ["feishu", "collaboration"]},
    }

    # ClawHub 集成配置
    CLAWHUB_AUTO_SEARCH: bool = True        # 本地技能匹配失败时自动搜索 ClawHub
    CLAWHUB_AUTO_INSTALL: bool = True       # 搜索到合适技能时自动安装
    CLAWHUB_SEARCH_LIMIT: int = 3           # 每次搜索返回的最大结果数
    CLAWHUB_MIN_CONFIDENCE: float = 0.6     # 自动安装的最低置信度阈值
    CLAWHUB_INSTALL_DIR: str = "./skills/installed"
    CLAWHUB_USE_MOCK: bool = False          # 使用真实 ClawHub CLI（支持速率限制重试）
    CLAWHUB_TIMEOUT: int = 60               # CLI 命令超时（秒）

    # ==================== HTTP 客户端配置 ====================
    # 连接池配置
    HTTP_MAX_CONNECTIONS: int = 100
    HTTP_MAX_KEEPALIVE_CONNECTIONS: int = 40
    HTTP_KEEPALIVE_EXPIRY: float = 30.0
    
    # 超时配置
    HTTP_CONNECT_TIMEOUT: float = 5.0
    HTTP_READ_TIMEOUT: float = 30.0
    HTTP_WRITE_TIMEOUT: float = 10.0
    HTTP_POOL_TIMEOUT: float = 5.0
    
    # 重试配置
    HTTP_MAX_RETRIES: int = 3
    HTTP_RETRY_DELAY: float = 1.0
    
    # HTTP/2 支持
    HTTP_ENABLE_HTTP2: bool = True
    
    # 限流配置
    HTTP_RATE_LIMIT: float = 20.0           # 默认请求速率（请求/秒）
    HTTP_MAX_CONCURRENT: int = 20           # 默认最大并发数
    HTTP_ADAPTIVE_RATE_LIMIT: bool = True   # 启用自适应限流
    HTTP_RATE_LIMIT_MIN: float = 1.0        # 最小速率
    HTTP_RATE_LIMIT_MAX: float = 50.0       # 最大速率

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

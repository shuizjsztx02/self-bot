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
    
    AGENT_MAX_ITERATIONS: int = 80
    RESEARCHER_MAX_ITERATIONS: int = 50

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

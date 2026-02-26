from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from typing import Optional
from app.config import settings


def get_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    **kwargs,
) -> BaseChatModel:
    provider = provider or settings.DEFAULT_LLM_PROVIDER
    
    configs = {
        "openai": {
            "model": model or settings.OPENAI_MODEL,
            "api_key": settings.OPENAI_API_KEY,
            "base_url": settings.OPENAI_BASE_URL,
        },
        "deepseek": {
            "model": model or settings.DEEPSEEK_MODEL,
            "api_key": settings.DEEPSEEK_API_KEY,
            "base_url": f"{settings.DEEPSEEK_BASE_URL}/v1",
        },
        "ollama": {
            "model": model or settings.OLLAMA_MODEL,
            "base_url": f"{settings.OLLAMA_BASE_URL}/v1",
            "api_key": "ollama",
        },
        "qwen": {
            "model": model or settings.QWEN_MODEL,
            "api_key": settings.QWEN_API_KEY,
            "base_url": settings.QWEN_BASE_URL,
        },
        "glm": {
            "model": model or settings.GLM_MODEL,
            "api_key": settings.GLM_API_KEY,
            "base_url": settings.GLM_BASE_URL,
        },
        "minimax": {
            "model": model or settings.MINIMAX_MODEL,
            "api_key": settings.MINIMAX_API_KEY,
            "base_url": settings.MINIMAX_BASE_URL,
        },
        "moonshot": {
            "model": model or settings.MOONSHOT_MODEL,
            "api_key": settings.MOONSHOT_API_KEY,
            "base_url": settings.MOONSHOT_BASE_URL,
        },
    }
    
    if provider not in configs:
        raise ValueError(f"Unknown provider: {provider}. Available: {list(configs.keys())}")
    
    config = configs[provider]
    config["temperature"] = temperature
    config.update(kwargs)
    
    return ChatOpenAI(**config)


def get_available_providers() -> list[str]:
    providers = []
    if settings.OPENAI_API_KEY:
        providers.append("openai")
    if settings.DEEPSEEK_API_KEY:
        providers.append("deepseek")
    if settings.QWEN_API_KEY:
        providers.append("qwen")
    if settings.GLM_API_KEY:
        providers.append("glm")
    if settings.MINIMAX_API_KEY:
        providers.append("minimax")
    if settings.MOONSHOT_API_KEY:
        providers.append("moonshot")
    providers.append("ollama")
    return providers


def get_provider_info() -> list[dict]:
    return [
        {
            "name": "openai",
            "model": settings.OPENAI_MODEL,
            "available": bool(settings.OPENAI_API_KEY),
            "base_url": settings.OPENAI_BASE_URL,
        },
        {
            "name": "deepseek",
            "model": settings.DEEPSEEK_MODEL,
            "available": bool(settings.DEEPSEEK_API_KEY),
            "base_url": settings.DEEPSEEK_BASE_URL,
        },
        {
            "name": "qwen",
            "model": settings.QWEN_MODEL,
            "available": bool(settings.QWEN_API_KEY),
            "base_url": settings.QWEN_BASE_URL,
        },
        {
            "name": "glm",
            "model": settings.GLM_MODEL,
            "available": bool(settings.GLM_API_KEY),
            "base_url": settings.GLM_BASE_URL,
        },
        {
            "name": "minimax",
            "model": settings.MINIMAX_MODEL,
            "available": bool(settings.MINIMAX_API_KEY),
            "base_url": settings.MINIMAX_BASE_URL,
        },
        {
            "name": "moonshot",
            "model": settings.MOONSHOT_MODEL,
            "available": bool(settings.MOONSHOT_API_KEY),
            "base_url": settings.MOONSHOT_BASE_URL,
        },
        {
            "name": "ollama",
            "model": settings.OLLAMA_MODEL,
            "available": True,
            "base_url": settings.OLLAMA_BASE_URL,
        },
    ]

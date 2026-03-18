# Self-Bot Backend Dockerfile
# 多阶段构建，优化镜像大小

# ==================== 基础镜像 ====================
FROM python:3.11-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ==================== 构建阶段 ====================
FROM base AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --user -r requirements.txt

# ==================== 运行阶段 ====================
FROM base AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    fonts-wqy-zenhei \
    fonts-wqy-microhei \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

RUN mkdir -p /app/data/database \
    /app/data/knowledge_base/documents \
    /app/data/knowledge_base/vectors \
    /app/data/knowledge_base/indexes \
    /app/data/agent/memories \
    /app/data/agent/vectors \
    /app/data/agent/traces \
    /app/workspace \
    /app/model_hub

COPY app/ ./app/
COPY prompts/ ./prompts/
COPY skills/ ./skills/
COPY mcp_servers/ ./mcp_servers/
COPY run.py .

ENV HOST=0.0.0.0 \
    PORT=8000 \
    DATABASE_URL=sqlite+aiosqlite:///./data/database/selfbot.db \
    WORKSPACE_PATH=/app/workspace \
    KB_DOCUMENT_PATH=/app/data/knowledge_base/documents \
    KB_VECTOR_PATH=/app/data/knowledge_base/vectors \
    KB_INDEX_PATH=/app/data/knowledge_base/indexes \
    AGENT_MEMORY_PATH=/app/data/agent/memories \
    AGENT_VECTOR_PATH=/app/data/agent/vectors \
    AGENT_TRACE_PATH=/app/data/agent/traces \
    MODEL_HUB_PATH=/app/model_hub

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "8000"]

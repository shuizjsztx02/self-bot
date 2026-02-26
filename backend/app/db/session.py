from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from app.config import settings
import os

db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
db_dir = os.path.dirname(db_path)
if db_dir and not os.path.exists(db_dir):
    os.makedirs(db_dir, exist_ok=True)

async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db():
    from app.langchain.models.database import Base
    from app.knowledge_base.models import Base as KBBase
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(KBBase.metadata.create_all)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


get_async_session = get_db


async def init_kb_tables():
    from app.knowledge_base.models import Base as KBBase
    async with async_engine.begin() as conn:
        await conn.run_sync(KBBase.metadata.create_all)

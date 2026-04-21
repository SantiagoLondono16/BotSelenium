from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
    echo=settings.app_env == "development",
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# ── Thread-safe session factory for background workers ────────────────────────
# Background threads create their own asyncio event loops.  asyncpg connections
# are bound to the loop that created them; sharing the main pool across loops
# causes "TCPTransport closed" errors when the bot loop is closed.
# NullPool never reuses connections, so each session gets a fresh connection
# that belongs only to the current event loop and is discarded after use.
_thread_engine = create_async_engine(
    settings.database_url,
    poolclass=NullPool,
    echo=settings.app_env == "development",
)

ThreadSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=_thread_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

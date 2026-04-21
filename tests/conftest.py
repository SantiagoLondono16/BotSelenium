"""
Shared pytest fixtures for all test modules.
Uses an in-memory SQLite database via aiosqlite for fast, isolated tests.
"""

import asyncio
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_session
from app.db.base import Base
from app.main import create_app

# ---------------------------------------------------------------------------
# Event-loop policy (required by pytest-asyncio for module/session scope)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()


# ---------------------------------------------------------------------------
# In-memory test database
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# FastAPI test client with overridden DB and mocked thread pool
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app = create_app()
    app.dependency_overrides[get_session] = override_get_db

    # Provide a real thread pool but don't actually run RPA in unit tests
    app.state.thread_pool = ThreadPoolExecutor(max_workers=1)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.state.thread_pool.shutdown(wait=False)

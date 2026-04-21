from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db():
        yield session


# Convenience alias for use in route dependencies
DBSession = Depends(get_session)

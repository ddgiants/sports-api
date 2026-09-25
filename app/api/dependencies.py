from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session


async def session_dependency() -> AsyncIterator[AsyncSession]:
    async for session in get_session():
        yield session

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import Settings


def create_database_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(settings.database_url, pool_pre_ping=True)


async def connection(engine: AsyncEngine) -> AsyncIterator:
    async with engine.connect() as database_connection:
        yield database_connection

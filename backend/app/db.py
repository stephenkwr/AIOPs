"""Async SQLAlchemy engine and session factory."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# statement_cache_size=0 disables asyncpg's prepared-statement cache, which is
# required when connecting through Supabase's transaction pooler (pgbouncer).
# Harmless locally against a direct connection.
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    connect_args={"statement_cache_size": 0},
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a database session."""
    async with SessionLocal() as session:
        yield session

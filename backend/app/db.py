"""Async SQLAlchemy engine and session factory."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings

# NullPool: don't pool connections client-side. In production we sit behind
# Supabase's transaction pooler (pgbouncer), which does the pooling — a second
# client-side pool on top of it conflicts with transaction mode. Locally it just
# means a fresh connection per request (negligible), and it keeps async
# connections from leaking across event loops in the test suite.
#
# statement_cache_size=0 disables asyncpg's prepared-statement cache, also
# required for pgbouncer transaction mode.
engine = create_async_engine(
    settings.database_url,
    echo=False,
    poolclass=NullPool,
    connect_args={"statement_cache_size": 0},
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a database session."""
    async with SessionLocal() as session:
        yield session

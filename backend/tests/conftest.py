import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import engine
from app.main import app


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def db_ready() -> None:
    """Skip a test when no database is reachable.

    In CI a Postgres service is always up, so DB-dependent tests run for real.
    On a bare local checkout without `docker compose up`, they skip instead of
    failing spuriously.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        pytest.skip("database not reachable")

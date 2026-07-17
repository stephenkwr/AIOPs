import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _hermetic_providers() -> None:
    """Force offline providers so tests never call Gemini/Groq, even when the
    developer's .env has real keys. Real providers are covered by a separate
    live smoke check, not the unit suite."""
    settings.embed_provider = "fake"
    settings.llm_provider = "fake"


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

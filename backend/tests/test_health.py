from httpx import AsyncClient


async def test_healthz(client: AsyncClient) -> None:
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_root(client: AsyncClient) -> None:
    r = await client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["app"] == "AI Operations Copilot"
    assert body["version"] == "0.1.0"


async def test_readyz(client: AsyncClient, db_ready: None) -> None:
    r = await client.get("/readyz")
    assert r.status_code == 200
    assert r.json() == {"status": "ready", "database": "ok"}

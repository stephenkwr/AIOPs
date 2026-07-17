from httpx import AsyncClient


async def test_list_orders_includes_seeded(client: AsyncClient, db_ready: None) -> None:
    r = await client.get("/api/v1/orders")
    assert r.status_code == 200
    numbers = {o["order_number"] for o in r.json()}
    assert {"1042", "1043", "1044"}.issubset(numbers)


async def test_get_single_order(client: AsyncClient, db_ready: None) -> None:
    r = await client.get("/api/v1/orders/1042")
    assert r.status_code == 200
    assert r.json()["status"] == "shipped"


async def test_get_missing_order_404(client: AsyncClient, db_ready: None) -> None:
    r = await client.get("/api/v1/orders/nope")
    assert r.status_code == 404


async def test_list_escalations(client: AsyncClient, db_ready: None) -> None:
    r = await client.get("/api/v1/escalations")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

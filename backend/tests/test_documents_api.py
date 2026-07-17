import asyncio

from httpx import AsyncClient


async def _wait_ready(client: AsyncClient, doc_id: str, tries: int = 50) -> dict:
    for _ in range(tries):
        r = await client.get(f"/api/v1/documents/{doc_id}")
        assert r.status_code == 200
        body = r.json()
        if body["status"] in ("ready", "failed"):
            return body
        await asyncio.sleep(0.1)
    raise AssertionError("document did not finish processing in time")


async def test_upload_and_process_csv(client: AsyncClient, db_ready: None) -> None:
    content = b"question,answer\nHow do I reset my password,Open Settings then Security\n"
    r = await client.post("/api/v1/documents", files={"file": ("faq.csv", content, "text/csv")})
    assert r.status_code == 201
    doc = r.json()
    assert doc["filename"] == "faq.csv"

    final = await _wait_ready(client, doc["id"])
    assert final["status"] == "ready", final.get("error")
    assert final["chunk_count"] >= 1


async def test_duplicate_upload_is_idempotent(client: AsyncClient, db_ready: None) -> None:
    content = b"col\nunique-value-for-idempotency-test\n"
    r1 = await client.post("/api/v1/documents", files={"file": ("d.csv", content, "text/csv")})
    r2 = await client.post("/api/v1/documents", files={"file": ("d.csv", content, "text/csv")})
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


async def test_unsupported_type_rejected(client: AsyncClient, db_ready: None) -> None:
    r = await client.post(
        "/api/v1/documents", files={"file": ("archive.zip", b"PK\x03\x04", "application/zip")}
    )
    assert r.status_code == 415


async def test_list_documents_returns_list(client: AsyncClient, db_ready: None) -> None:
    r = await client.get("/api/v1/documents")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

import asyncio

from httpx import AsyncClient

from app.constants import DEMO_WORKSPACE_ID
from app.core.retrieval.retriever import retrieve
from app.db import SessionLocal


async def _upload_and_wait(client: AsyncClient, name: str, content: bytes) -> None:
    r = await client.post("/api/v1/documents", files={"file": (name, content, "text/plain")})
    assert r.status_code == 201
    doc_id = r.json()["id"]
    for _ in range(50):
        body = (await client.get(f"/api/v1/documents/{doc_id}")).json()
        if body["status"] in ("ready", "failed"):
            assert body["status"] == "ready", body.get("error")
            return
        await asyncio.sleep(0.1)
    raise AssertionError("document did not become ready")


async def test_hybrid_retrieval_finds_relevant_chunk(client: AsyncClient, db_ready: None) -> None:
    await _upload_and_wait(
        client,
        "passwords.txt",
        b"To reset your password, open Settings then Security and click Reset Password.",
    )
    await _upload_and_wait(
        client,
        "shipping.txt",
        b"Standard shipping takes five to seven business days for domestic orders.",
    )

    async with SessionLocal() as session:
        results = await retrieve(
            session, DEMO_WORKSPACE_ID, "how do I reset my password", mode="hybrid", k=3
        )

    assert results
    assert results[0].index == 1
    assert "password" in results[0].text.lower()


async def test_vector_mode_returns_results(client: AsyncClient, db_ready: None) -> None:
    await _upload_and_wait(client, "vec.txt", b"Escalations are routed to the on-call engineer.")
    async with SessionLocal() as session:
        results = await retrieve(
            session, DEMO_WORKSPACE_ID, "who handles escalations", mode="vector", k=3
        )
    assert results
    assert all(r.vector_similarity >= 0.0 for r in results)

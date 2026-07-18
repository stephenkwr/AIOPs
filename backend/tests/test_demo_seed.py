"""The "Load demo data" endpoint: seeds the Aurora KB into the demo workspace."""

import asyncio

from httpx import AsyncClient
from sqlalchemy import func, select, text, update

from app.constants import DEMO_WORKSPACE_ID
from app.db import SessionLocal
from app.models import Chunk, Document


async def _demo_doc_count(status: str | None = None) -> int:
    async with SessionLocal() as s:
        q = select(func.count(Document.id)).where(Document.workspace_id == DEMO_WORKSPACE_ID)
        if status:
            q = q.where(Document.status == status)
        return int(await s.scalar(q) or 0)


async def test_demo_seed_is_idempotent(client: AsyncClient, db_ready: None) -> None:
    r = await client.post("/api/v1/demo/seed")
    assert r.status_code == 200
    body = r.json()
    assert body["queued"] + body["skipped"] == 12
    assert len(body["suggested_questions"]) >= 3

    # Background ingestion runs after the response; wait for it to settle.
    for _ in range(100):
        ready = await _demo_doc_count("ready")
        if ready >= 12:
            break
        await asyncio.sleep(0.2)

    before = await _demo_doc_count()

    # Second call: everything already present, nothing new created.
    r2 = await client.post("/api/v1/demo/seed")
    assert r2.status_code == 200
    assert r2.json()["queued"] == 0
    assert r2.json()["skipped"] == 12
    assert await _demo_doc_count() == before


async def test_demo_seed_reembeds_on_provider_change(client: AsyncClient, db_ready: None) -> None:
    await client.post("/api/v1/demo/seed")
    for _ in range(100):
        if await _demo_doc_count("ready") >= 12:
            break
        await asyncio.sleep(0.2)

    # Simulate one CORPUS doc embedded by a different provider (the demo workspace
    # also holds user uploads — those must never be touched by the reconciler).
    async with SessionLocal() as s:
        doc = await s.scalar(
            select(Document).where(
                Document.workspace_id == DEMO_WORKSPACE_ID,
                Document.filename == "gift-cards.md",
                Document.status == "ready",
            )
        )
        assert doc is not None
        await s.execute(
            update(Chunk)
            .where(Chunk.document_id == doc.id)
            .values(meta={"filename": doc.filename, "embedder": "other@768"})
        )
        await s.commit()

    r = await client.post("/api/v1/demo/seed")
    assert r.status_code == 200
    assert r.json()["queued"] == 1  # just the stale doc, user docs untouched
    assert r.json()["skipped"] == 11


async def test_demo_seed_recovers_stuck_ingest(client: AsyncClient, db_ready: None) -> None:
    """A doc that crashed mid-ingest (old, non-ready) is re-staged; a fresh
    in-flight one is left alone."""
    await client.post("/api/v1/demo/seed")
    for _ in range(100):
        if await _demo_doc_count("ready") >= 12:
            break
        await asyncio.sleep(0.2)

    async with SessionLocal() as s:
        doc = await s.scalar(
            select(Document).where(
                Document.workspace_id == DEMO_WORKSPACE_ID,
                Document.filename == "warranty.md",
                Document.status == "ready",
            )
        )
        assert doc is not None
        # Simulate a crash one hour ago, mid-embedding.
        await s.execute(
            update(Document)
            .where(Document.id == doc.id)
            .values(status="embedding", updated_at=func.now() - text("interval '1 hour'"))
        )
        await s.commit()

    r = await client.post("/api/v1/demo/seed")
    assert r.status_code == 200
    assert r.json()["queued"] == 1
    for _ in range(100):
        if await _demo_doc_count("ready") >= 12:
            break
        await asyncio.sleep(0.2)
    assert await _demo_doc_count("ready") >= 12

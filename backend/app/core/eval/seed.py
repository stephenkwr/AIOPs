"""Seed the fixed eval corpus into the isolated eval workspace (idempotent).

Reuses the real ingestion pipeline (parse -> chunk -> embed -> persist) so the eval
measures the same retrieval path the product uses, not a shortcut.

The seeder RECONCILES the workspace against the version-controlled corpus rather
than just inserting: a doc is re-ingested when its file was edited (sha changed),
dropped when its file was removed, and — critically — re-embedded when the
configured embedder differs from the one that produced its stored vectors
(chunk meta carries an "embedder" provenance stamp). Without that last check, a
provider change (e.g. adding a GEMINI_API_KEY after an offline seed) would leave
corpus vectors in a different vector space than query vectors, and vector/hybrid
retrieval would silently return garbage.
"""

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.constants import EVAL_WORKSPACE_ID
from app.core.eval.dataset import load_corpus
from app.core.ingestion.embedder import get_embedder
from app.core.ingestion.pipeline import process_document
from app.core.storage import get_storage
from app.db import SessionLocal
from app.models import Chunk, Document, Workspace


async def _ensure_eval_workspace(session: AsyncSession) -> None:
    ws = await session.get(Workspace, EVAL_WORKSPACE_ID)
    if ws is None:
        session.add(Workspace(id=EVAL_WORKSPACE_ID, name="eval"))
        await session.commit()


async def _doc_embedder(session: AsyncSession, document_id: uuid.UUID) -> str | None:
    """The embedder provenance stamp on the doc's chunks (None on pre-stamp docs)."""
    meta = await session.scalar(select(Chunk.meta).where(Chunk.document_id == document_id).limit(1))
    return (meta or {}).get("embedder")


async def seed_eval_corpus(
    session_factory: async_sessionmaker[AsyncSession] = SessionLocal,
) -> dict:
    """Sync the eval workspace to the corpus on disk. Returns what changed."""
    corpus = load_corpus()
    shas = {cf.filename: hashlib.sha256(cf.text.encode("utf-8")).hexdigest() for cf in corpus}
    embedder_id = get_embedder().identity

    seeded: list[str] = []
    skipped: list[str] = []
    removed: list[str] = []
    to_process: list[uuid.UUID] = []

    async with session_factory() as session:
        await _ensure_eval_workspace(session)

        # Reconcile existing docs against the corpus + current embedder.
        existing = (
            await session.scalars(
                select(Document).where(Document.workspace_id == EVAL_WORKSPACE_ID)
            )
        ).all()
        current: set[str] = set()
        for doc in existing:
            expected_sha = shas.get(doc.filename)
            stale = (
                expected_sha is None  # file removed from the corpus
                or doc.sha256 != expected_sha  # file edited
                or doc.status != "ready"  # partial ingest from a prior failed run
                or await _doc_embedder(session, doc.id) != embedder_id  # provider changed
            )
            if stale:
                await session.delete(doc)  # chunks cascade
                removed.append(doc.filename)
            else:
                current.add(doc.filename)
        await session.commit()

        for cf in corpus:
            if cf.filename in current:
                skipped.append(cf.filename)
                continue
            data = cf.text.encode("utf-8")
            sha = shas[cf.filename]
            key = f"{EVAL_WORKSPACE_ID}/{sha}.txt"
            get_storage().save(key, data)
            doc = Document(
                workspace_id=EVAL_WORKSPACE_ID,
                filename=cf.filename,
                mime_type="text/markdown",
                sha256=sha,
                storage_path=key,
                status="uploaded",
            )
            session.add(doc)
            await session.commit()
            await session.refresh(doc)
            to_process.append(doc.id)
            seeded.append(cf.filename)

    # process_document opens its own session per doc (mirrors the upload path).
    for doc_id in to_process:
        await process_document(doc_id, session_factory)

    return {"seeded": seeded, "skipped": skipped, "removed": removed, "total": len(corpus)}

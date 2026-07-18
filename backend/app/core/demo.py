"""One-click demo data: load the Aurora KB into the demo workspace.

A visitor landing on an empty app has nothing to ask about. This stages the same
version-controlled corpus the eval uses (so the copilot's answers are verifiable
against the golden dataset) into the DEMO workspace, without ever touching or
deleting anything the user uploaded themselves — inserts are keyed by content
sha, so re-running is a no-op.
"""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import DEMO_WORKSPACE_ID
from app.core.eval.dataset import load_corpus
from app.core.ingestion.embedder import get_embedder
from app.core.storage import get_storage
from app.models import Chunk, Document

SUGGESTED_QUESTIONS = [
    "How do I reset my password?",
    "How long do refunds take to appear?",
    "What's the status of order 1042?",
    "Do you price-match other retailers?",  # unanswerable -> the copilot should escalate
]

# An in-progress doc older than this is a crashed ingest, not an active one.
STUCK_AFTER = timedelta(minutes=10)


async def _doc_embedder(session: AsyncSession, document_id: uuid.UUID) -> str | None:
    meta = await session.scalar(select(Chunk.meta).where(Chunk.document_id == document_id).limit(1))
    return (meta or {}).get("embedder")


async def _is_stale(session: AsyncSession, doc: Document, embedder_id: str) -> bool:
    if doc.status == "failed":
        return True
    if doc.status == "ready":
        return await _doc_embedder(session, doc.id) != embedder_id
    # In-progress (uploaded/parsing/chunking/embedding): a fresh one is a live
    # background ingest — leave it alone; an old one crashed mid-flight — redo it.
    return doc.updated_at < datetime.now(UTC) - STUCK_AFTER


async def stage_demo_documents(session: AsyncSession) -> tuple[list[uuid.UUID], list[str]]:
    """Create Document rows for corpus files missing from the demo workspace.

    Returns (doc ids to process, skipped filenames). Processing itself runs as a
    background task per document — same as a real upload. A corpus doc whose stored
    vectors came from a different embedder, or that failed / got stuck mid-ingest,
    is re-ingested (matched by content sha, so user uploads are never touched);
    see the eval seeder for why the embedder check matters.
    """
    embedder_id = get_embedder().identity
    to_process: list[uuid.UUID] = []
    skipped: list[str] = []

    for cf in load_corpus():
        data = cf.text.encode("utf-8")
        sha = hashlib.sha256(data).hexdigest()
        existing = await session.scalar(
            select(Document).where(
                Document.workspace_id == DEMO_WORKSPACE_ID, Document.sha256 == sha
            )
        )
        if existing is not None:
            if not await _is_stale(session, existing, embedder_id):
                skipped.append(cf.filename)
                continue
            await session.delete(existing)  # chunks cascade; re-staged below
            await session.flush()

        key = f"{DEMO_WORKSPACE_ID}/{sha}.txt"
        get_storage().save(key, data)
        doc = Document(
            workspace_id=DEMO_WORKSPACE_ID,
            filename=cf.filename,
            mime_type="text/markdown",
            sha256=sha,
            storage_path=key,
            status="uploaded",
        )
        session.add(doc)
        # Commit per doc: a concurrent seed inserting the same sha loses the
        # unique-constraint race for that one doc only, not the whole request.
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            skipped.append(cf.filename)
            continue
        to_process.append(doc.id)

    return to_process, skipped

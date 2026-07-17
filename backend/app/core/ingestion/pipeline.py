"""The ingestion pipeline: parse -> chunk -> embed -> persist.

Runs as a background task with its OWN database session (never the request
session). Status is committed at each stage so the UI can watch progress, and any
failure is isolated to the single document (status=failed + error recorded).

The enqueue/poll shape here is deliberately queue-like: swapping BackgroundTasks
for Celery/SQS later changes only how process_document is invoked, not its body.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.core.ingestion.chunker import chunk_document
from app.core.ingestion.embedder import get_embedder
from app.core.ingestion.parsers import parse
from app.core.storage import get_storage
from app.db import SessionLocal
from app.models import Chunk, Document


async def _set_status(session: AsyncSession, doc: Document, status: str) -> None:
    doc.status = status
    await session.commit()


async def process_document(
    document_id: uuid.UUID,
    session_factory: async_sessionmaker[AsyncSession] = SessionLocal,
) -> None:
    async with session_factory() as session:
        doc = await session.get(Document, document_id)
        if doc is None:
            return
        try:
            data = get_storage().load(doc.storage_path)

            await _set_status(session, doc, "parsing")
            parsed = parse(data, doc.mime_type, doc.filename)
            doc.page_count = parsed.page_count

            await _set_status(session, doc, "chunking")
            chunks = chunk_document(
                parsed,
                strategy=settings.chunker,
                target_tokens=settings.chunk_target_tokens,
                overlap_ratio=settings.chunk_overlap_ratio,
                base_meta={"filename": doc.filename},
            )
            if not chunks:
                raise ValueError("No text could be extracted from this document")

            await _set_status(session, doc, "embedding")
            vectors = await get_embedder().embed([c.text for c in chunks])

            for chunk, vector in zip(chunks, vectors, strict=True):
                session.add(
                    Chunk(
                        document_id=doc.id,
                        workspace_id=doc.workspace_id,
                        ord=chunk.ord,
                        text=chunk.text,
                        token_count=chunk.token_count,
                        embedding=vector,
                        meta=chunk.meta,
                    )
                )
            doc.chunk_count = len(chunks)
            doc.status = "ready"
            doc.error = None
            await session.commit()
        except Exception as exc:  # noqa: BLE001 — record any failure, isolate the doc
            await session.rollback()
            failed = await session.get(Document, document_id)
            if failed is not None:
                failed.status = "failed"
                failed.error = str(exc)[:500]
                await session.commit()

"""Document upload & management endpoints."""

import hashlib
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.ingestion.parsers import detect_kind
from app.core.ingestion.pipeline import process_document
from app.core.storage import get_storage
from app.db import get_session
from app.deps import get_workspace_id
from app.limits import UPLOAD_LIMIT, limiter
from app.models import Document
from app.schemas.document import DocumentOut

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.post("", response_model=DocumentOut, status_code=201)
@limiter.limit(UPLOAD_LIMIT)
async def upload_document(
    request: Request,
    background: BackgroundTasks,
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    workspace_id: uuid.UUID = Depends(get_workspace_id),
) -> Document:
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_upload_mb} MB")

    kind = detect_kind(file.content_type or "", file.filename or "")
    if kind is None:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {file.content_type}")

    # Idempotency: identical content in the same workspace is a no-op.
    sha256 = hashlib.sha256(data).hexdigest()
    existing = await session.scalar(
        select(Document).where(Document.workspace_id == workspace_id, Document.sha256 == sha256)
    )
    if existing is not None:
        return existing

    key = f"{workspace_id}/{sha256}.{kind}"
    get_storage().save(key, data)

    doc = Document(
        workspace_id=workspace_id,
        filename=file.filename or f"upload.{kind}",
        mime_type=file.content_type or f"application/{kind}",
        sha256=sha256,
        storage_path=key,
        status="uploaded",
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    # Enqueue processing. Under a real queue this becomes queue.enqueue(...).
    background.add_task(process_document, doc.id)
    return doc


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    session: AsyncSession = Depends(get_session),
    workspace_id: uuid.UUID = Depends(get_workspace_id),
) -> list[Document]:
    rows = await session.scalars(
        select(Document)
        .where(Document.workspace_id == workspace_id)
        .order_by(Document.created_at.desc())
    )
    return list(rows)


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    workspace_id: uuid.UUID = Depends(get_workspace_id),
) -> Document:
    doc = await session.get(Document, document_id)
    if doc is None or doc.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    workspace_id: uuid.UUID = Depends(get_workspace_id),
) -> None:
    doc = await session.get(Document, document_id)
    if doc is None or doc.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        get_storage().delete(doc.storage_path)
    except OSError:
        pass  # best-effort; the DB row is the source of truth
    await session.delete(doc)  # chunks cascade
    await session.commit()

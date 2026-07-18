"""Demo workspace seeding — the "Load demo data" button."""

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.demo import SUGGESTED_QUESTIONS, stage_demo_documents
from app.core.ingestion.pipeline import process_document
from app.db import get_session
from app.limits import DEMO_SEED_LIMIT, limiter

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


class DemoSeedResult(BaseModel):
    queued: int
    skipped: int
    suggested_questions: list[str]


@router.post("/seed", response_model=DemoSeedResult)
@limiter.limit(DEMO_SEED_LIMIT)
async def seed_demo(
    request: Request,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> DemoSeedResult:
    """Load the Aurora support KB into the demo workspace (idempotent).

    Documents ingest in the background — the Documents page shows each one move
    through parsing → chunking → embedding → ready, exactly like a real upload.
    """
    to_process, skipped = await stage_demo_documents(session)
    for doc_id in to_process:
        background.add_task(process_document, doc_id)
    return DemoSeedResult(
        queued=len(to_process),
        skipped=len(skipped),
        suggested_questions=SUGGESTED_QUESTIONS,
    )

"""Evaluation endpoints: inspect the golden dataset, launch runs, read results.

Eval operates on the fixed eval workspace (not the user's demo workspace), so these
endpoints are global rather than workspace-scoped.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.eval.dataset import load_corpus, load_dataset
from app.core.eval.runner import run_eval
from app.db import get_session
from app.models import EvalCase, EvalRun
from app.schemas.eval import (
    DatasetInfo,
    DatasetItemOut,
    EvalCaseOut,
    EvalRunDetail,
    EvalRunSummary,
    EvalStartRequest,
)

router = APIRouter(prefix="/api/v1/eval", tags=["eval"])


@router.get("/dataset", response_model=DatasetInfo)
async def get_dataset() -> DatasetInfo:
    name, items = load_dataset()
    corpus_docs = [cf.filename for cf in load_corpus()]
    answerable = sum(1 for it in items if it.answerable)
    return DatasetInfo(
        name=name,
        total=len(items),
        answerable=answerable,
        unanswerable=len(items) - answerable,
        corpus_docs=corpus_docs,
        items=[
            DatasetItemOut(
                id=it.id,
                question=it.question,
                category=it.category,
                answerable=it.answerable,
                gold_doc=it.gold_doc,
                reference_answer=it.reference_answer,
            )
            for it in items
        ],
    )


@router.get("/runs", response_model=list[EvalRunSummary])
async def list_eval_runs(session: AsyncSession = Depends(get_session)) -> list[EvalRun]:
    rows = await session.scalars(select(EvalRun).order_by(EvalRun.created_at.desc()).limit(100))
    return list(rows)


@router.get("/runs/{run_id}", response_model=EvalRunDetail)
async def get_eval_run(
    run_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> EvalRunDetail:
    run = await session.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Eval run not found")
    cases = await session.scalars(
        select(EvalCase).where(EvalCase.eval_run_id == run_id).order_by(EvalCase.case_id)
    )
    return EvalRunDetail(
        **EvalRunSummary.model_validate(run).model_dump(),
        failure_reason=run.failure_reason,
        cases=[EvalCaseOut.model_validate(c) for c in cases],
    )


@router.post("/runs", response_model=EvalRunSummary, status_code=201)
async def start_eval_run(
    body: EvalStartRequest,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> EvalRun:
    name, _items = load_dataset()
    label = body.label or (
        f"{body.retrieval_mode} · k={body.k}" + (" · graded" if body.graded else "")
    )
    run = EvalRun(
        label=label,
        dataset=name,
        retrieval_mode=body.retrieval_mode,
        k=body.k,
        graded=body.graded,
        status="running",
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    # Under a real queue this becomes queue.enqueue(...); the runner body is unchanged.
    background.add_task(
        run_eval,
        run.id,
        retrieval_mode=body.retrieval_mode,
        k=body.k,
        graded=body.graded,
        limit=body.limit,
    )
    return run

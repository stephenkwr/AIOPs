"""The eval runner: score the golden dataset under one configuration.

Retrieval is always scored (deterministic, no LLM). When graded=True it also
generates an answer per question and grades it (groundedness / correctness /
refusal), which is what surfaces the downstream answer-quality lift of better
retrieval.
"""

import uuid

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.constants import EVAL_WORKSPACE_ID
from app.core.answer import build_messages
from app.core.eval.dataset import load_dataset
from app.core.eval.judge import Grade, heuristic_grade, llm_grade
from app.core.eval.metrics import looks_like_refusal, retrieval_metrics
from app.core.eval.seed import seed_eval_corpus
from app.core.llm.base import collect
from app.core.llm.factory import get_answer_client, get_judge_client
from app.core.retrieval.retriever import retrieve
from app.db import SessionLocal
from app.models import EvalCase, EvalRun

GROUNDED_MIN = 0.5
CORRECT_MIN = 0.5
ANSWER_MAX_TOKENS = 512


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def _case_correct(answerable: bool, refused: bool, grade: Grade) -> bool:
    if not answerable:
        return refused  # the right move for an unanswerable question is to refuse
    return (not refused) and grade.correctness >= CORRECT_MIN and grade.groundedness >= GROUNDED_MIN


def _aggregate(cases: list[EvalCase], graded: bool) -> dict:
    answerable = [c for c in cases if c.answerable]
    unanswerable = [c for c in cases if not c.answerable]

    metrics: dict = {
        "n_cases": len(cases),
        "n_answerable": len(answerable),
        "n_unanswerable": len(unanswerable),
        # Retrieval (over answerable, which carry gold labels)
        "hit_at_k": _mean([1.0 if c.hit else 0.0 for c in answerable]),
        "mrr": _mean([float(c.reciprocal_rank) for c in answerable]),
    }

    if graded:
        # A case whose grading errored carries judge={"error": ...} — exclude it from
        # the score means (it still counts as a failure in the accuracy rates below).
        graded_ans = [c for c in answerable if c.judge and "groundedness" in c.judge]
        metrics["groundedness"] = _mean([c.judge["groundedness"] for c in graded_ans])
        metrics["correctness"] = _mean([c.judge["correctness"] for c in graded_ans])
        metrics["n_grading_errors"] = sum(
            1 for c in cases if c.judge is not None and "error" in c.judge
        )
        metrics["answer_accuracy"] = _mean([1.0 if c.correct else 0.0 for c in answerable])
        metrics["refusal_accuracy"] = _mean([1.0 if c.correct else 0.0 for c in unanswerable])
        metrics["pass_rate"] = _mean([1.0 if c.correct else 0.0 for c in cases])

    return metrics


async def run_eval(
    eval_run_id: uuid.UUID,
    *,
    retrieval_mode: str,
    k: int,
    graded: bool,
    limit: int | None = None,
    session_factory: async_sessionmaker[AsyncSession] = SessionLocal,
) -> None:
    """Execute an eval run to completion, persisting per-case rows + aggregates."""
    try:
        await seed_eval_corpus(session_factory)
        _name, items = load_dataset()
        if limit is not None:
            items = items[:limit]

        answer_client = get_answer_client() if graded else None
        judge_client = None
        answer_model = None
        if graded:
            answer_model = getattr(answer_client, "model", None)
            judge_client = get_judge_client(avoid_model=answer_model)

        built: list[EvalCase] = []
        async with session_factory() as session:
            for item in items:
                retrieved = await retrieve(
                    session,
                    EVAL_WORKSPACE_ID,
                    item.question,
                    mode=retrieval_mode,
                    k=k,
                    candidates=settings.retrieval_candidates,
                )
                filenames = [r.filename for r in retrieved]
                hit, rank, rr = retrieval_metrics(item.gold_doc, filenames, k)

                case = EvalCase(
                    eval_run_id=eval_run_id,
                    case_id=item.id,
                    question=item.question,
                    category=item.category,
                    answerable=item.answerable,
                    gold_doc=item.gold_doc,
                    retrieved=filenames,
                    hit=hit,
                    rank=rank,
                    reciprocal_rank=rr,
                )

                if graded and answer_client is not None:
                    try:
                        messages = build_messages(item.question, retrieved)
                        answer, _usage = await collect(
                            answer_client.stream(messages, max_tokens=ANSWER_MAX_TOKENS)
                        )
                        answer = answer.strip()
                        if answer_model is None:
                            answer_model = (
                                getattr(answer_client, "last_model", None) or answer_client.model
                            )
                        grade = (
                            await llm_grade(judge_client, item, retrieved, answer)
                            if judge_client is not None
                            else heuristic_grade(item, retrieved, answer)
                        )
                        case.answer = answer
                        case.refused = grade.refused or looks_like_refusal(answer)
                        case.judge = {
                            "groundedness": grade.groundedness,
                            "correctness": grade.correctness,
                            "reasoning": grade.reasoning,
                        }
                        case.correct = _case_correct(item.answerable, case.refused, grade)
                    except Exception as exc:  # noqa: BLE001 — isolate one bad case
                        case.answer = None
                        case.refused = False
                        case.judge = {"error": str(exc)[:200]}
                        case.correct = False

                session.add(case)
                built.append(case)

            run = await session.get(EvalRun, eval_run_id)
            if run is not None:
                run.num_cases = len(built)
                run.metrics = _aggregate(built, graded)
                run.answer_model = answer_model
                run.judge_model = (
                    getattr(judge_client, "model", None) if judge_client else None
                ) or ("heuristic" if graded else None)
                run.status = "completed"
                run.finished_at = func.now()
            await session.commit()
    except Exception as exc:  # noqa: BLE001 — record run-level failure
        async with session_factory() as session:
            run = await session.get(EvalRun, eval_run_id)
            if run is not None:
                run.status = "failed"
                run.failure_reason = str(exc)[:500]
                run.finished_at = func.now()
                await session.commit()

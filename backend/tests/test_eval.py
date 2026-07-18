"""Eval harness: pure metrics, dataset integrity, the runner, seeding, and the API."""

import uuid

from httpx import AsyncClient
from sqlalchemy import select, update

from app.constants import EVAL_WORKSPACE_ID
from app.core.eval.dataset import load_corpus, load_dataset
from app.core.eval.metrics import looks_like_refusal, retrieval_metrics, token_recall
from app.core.eval.runner import _aggregate, run_eval
from app.core.eval.seed import seed_eval_corpus
from app.db import SessionLocal
from app.models import Chunk, Document, EvalCase, EvalRun

# --- pure metrics (no DB) --------------------------------------------------


def test_retrieval_metrics_hit_and_rank() -> None:
    hit, rank, rr = retrieval_metrics("refunds.md", ["shipping.md", "refunds.md", "x.md"], k=8)
    assert hit and rank == 2 and rr == 0.5


def test_retrieval_metrics_miss_and_outside_k() -> None:
    # gold present but beyond k -> miss
    hit, rank, rr = retrieval_metrics("refunds.md", ["a.md", "b.md", "refunds.md"], k=2)
    assert not hit and rank is None and rr == 0.0
    # no gold label at all (unanswerable)
    assert retrieval_metrics(None, ["a.md"], k=8) == (False, None, 0.0)


def test_token_recall_and_refusal() -> None:
    assert token_recall("refunds take five business days", "refunds five days") > 0.5
    assert looks_like_refusal("I don't have that information — I'll escalate to a human.")
    assert not looks_like_refusal("Standard shipping takes 4 to 6 business days.")


def test_aggregate_isolates_grading_errors() -> None:
    """A case whose grading errored (judge={'error':...}) must not crash aggregation."""

    def case(judge: dict | None, correct: bool | None) -> EvalCase:
        return EvalCase(
            case_id="x",
            question="q",
            category="c",
            answerable=True,
            gold_doc="d.md",
            hit=True,
            rank=1,
            reciprocal_rank=1.0,
            refused=False,
            judge=judge,
            correct=correct,
        )

    ok = case({"groundedness": 1.0, "correctness": 0.8}, True)
    errored = case({"error": "judge timed out"}, False)
    metrics = _aggregate([ok, errored], graded=True)

    assert metrics["groundedness"] == 1.0  # error case excluded from score means
    assert metrics["correctness"] == 0.8
    assert metrics["answer_accuracy"] == 0.5  # …but still counts as a failure
    assert metrics["n_grading_errors"] == 1


# --- dataset integrity (no DB) ---------------------------------------------


def test_dataset_loads_and_gold_docs_exist() -> None:
    name, items = load_dataset()
    assert name and len(items) >= 60
    corpus = {cf.filename for cf in load_corpus()}
    assert len(corpus) >= 10
    for it in items:
        if it.answerable:
            assert it.gold_doc in corpus, f"{it.id} references missing doc {it.gold_doc}"
            assert it.reference_answer
        else:
            assert it.gold_doc is None


# --- runner (DB) -----------------------------------------------------------


async def _make_run(mode: str, graded: bool, limit: int | None) -> uuid.UUID:
    async with SessionLocal() as s:
        run = EvalRun(
            label=f"test-{mode}",
            dataset="t",
            retrieval_mode=mode,
            k=8,
            graded=graded,
            status="running",
        )
        s.add(run)
        await s.commit()
        await s.refresh(run)
        rid = run.id
    await run_eval(rid, retrieval_mode=mode, k=8, graded=graded, limit=limit)
    return rid


async def test_runner_retrieval_only_keyword(db_ready: None) -> None:
    rid = await _make_run("keyword", graded=False, limit=None)
    async with SessionLocal() as s:
        run = await s.get(EvalRun, rid)
        cases = (await s.scalars(select(EvalCase).where(EvalCase.eval_run_id == rid))).all()

    assert run.status == "completed"
    assert run.num_cases == len(cases) >= 60
    m = run.metrics
    assert 0.0 <= m["hit_at_k"] <= 1.0
    assert m["hit_at_k"] > 0  # full-text search matches the corpus vocabulary
    assert 0.0 <= m["mrr"] <= 1.0
    # retrieval-only runs don't grade answers
    assert "answer_accuracy" not in m
    # unanswerable cases carry no gold and never "hit"
    for c in cases:
        if not c.answerable:
            assert c.gold_doc is None and not c.hit


async def test_runner_graded_populates_judge(db_ready: None) -> None:
    rid = await _make_run("hybrid", graded=True, limit=8)
    async with SessionLocal() as s:
        run = await s.get(EvalRun, rid)
        cases = (await s.scalars(select(EvalCase).where(EvalCase.eval_run_id == rid))).all()

    assert run.status == "completed"
    assert run.judge_model  # heuristic offline
    m = run.metrics
    for key in ("groundedness", "correctness", "answer_accuracy", "refusal_accuracy", "pass_rate"):
        assert key in m
    graded_cases = [c for c in cases if c.answerable and c.judge]
    assert graded_cases
    for c in graded_cases:
        assert "groundedness" in c.judge and "correctness" in c.judge
        assert c.correct in (True, False)


# --- seeder reconciliation (DB) ---------------------------------------------


async def test_seeder_reconciles_stale_docs(db_ready: None) -> None:
    # Baseline: everything seeded and then stable.
    await seed_eval_corpus()
    second = await seed_eval_corpus()
    assert second["seeded"] == [] and len(second["skipped"]) >= 10

    async with SessionLocal() as s:
        docs = (
            await s.scalars(select(Document).where(Document.workspace_id == EVAL_WORKSPACE_ID))
        ).all()
        edited, ghost_target = docs[0], docs[1]
        edited_name, ghost_name = edited.filename, "ghost.md"

        # Simulate an edited corpus file (stored sha no longer matches disk)…
        edited.sha256 = "0" * 64
        # …a doc whose file was removed from the corpus…
        ghost_target.filename = ghost_name
        # …and a doc embedded by a different provider (stale vector space).
        mismatch = docs[2]
        mismatch_name = mismatch.filename
        await s.execute(
            update(Chunk)
            .where(Chunk.document_id == mismatch.id)
            .values(meta={"filename": mismatch_name, "embedder": "other@768"})
        )
        await s.commit()

    result = await seed_eval_corpus()
    # ghost.md dropped and not re-seeded; the other two re-ingested fresh.
    assert ghost_name in result["removed"]
    assert edited_name in result["seeded"]
    assert mismatch_name in result["seeded"]

    async with SessionLocal() as s:
        names = set(
            (
                await s.scalars(
                    select(Document.filename).where(
                        Document.workspace_id == EVAL_WORKSPACE_ID,
                        Document.status == "ready",
                    )
                )
            ).all()
        )
    assert ghost_name not in names
    assert {edited_name, mismatch_name} <= names


# --- API (DB) --------------------------------------------------------------


async def test_dataset_endpoint(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/eval/dataset")).json()
    assert body["total"] == body["answerable"] + body["unanswerable"]
    assert body["answerable"] >= 60
    assert len(body["corpus_docs"]) >= 10
    assert len(body["items"]) == body["total"]


async def test_start_and_read_eval_run(client: AsyncClient, db_ready: None) -> None:
    r = await client.post(
        "/api/v1/eval/runs", json={"retrieval_mode": "keyword", "k": 5, "limit": 20}
    )
    assert r.status_code == 201
    rid = r.json()["id"]

    # background task runs the eval; poll until it settles
    detail = None
    for _ in range(100):
        detail = (await client.get(f"/api/v1/eval/runs/{rid}")).json()
        if detail["status"] in ("completed", "failed"):
            break
    assert detail["status"] == "completed"
    assert detail["metrics"]["hit_at_k"] is not None
    assert len(detail["cases"]) == 20

    listing = (await client.get("/api/v1/eval/runs")).json()
    assert any(run["id"] == rid for run in listing)

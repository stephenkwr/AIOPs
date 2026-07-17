import asyncio
import json

from httpx import AsyncClient
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Escalation, RunStep


async def _upload_and_wait(client: AsyncClient, name: str, content: bytes) -> None:
    r = await client.post("/api/v1/documents", files={"file": (name, content, "text/plain")})
    doc_id = r.json()["id"]
    for _ in range(50):
        body = (await client.get(f"/api/v1/documents/{doc_id}")).json()
        if body["status"] in ("ready", "failed"):
            return
        await asyncio.sleep(0.1)


async def _collect(resp) -> list[tuple[str, dict | None]]:
    events: list[tuple[str, dict | None]] = []
    name: str | None = None
    data: str | None = None
    async for line in resp.aiter_lines():
        if line.startswith("event:"):
            name = line[6:].strip()
        elif line.startswith("data:"):
            data = line[5:].strip()
        elif line == "":
            if name is not None:
                events.append((name, json.loads(data) if data else None))
            name, data = None, None
    return events


async def _agent(client: AsyncClient, conv_id: str, question: str):
    async with client.stream(
        "POST", f"/api/v1/conversations/{conv_id}/agent", json={"question": question}
    ) as resp:
        assert resp.status_code == 200
        return await _collect(resp)


async def test_agent_run_uses_kb_and_completes(client: AsyncClient, db_ready: None) -> None:
    await _upload_and_wait(client, "kb.txt", b"To reset your password open Settings then Security.")
    conv = (await client.post("/api/v1/conversations", json={})).json()

    events = await _agent(client, conv["id"], "How do I reset my password?")
    kinds = [k for k, _ in events]
    assert "run" in kinds
    assert "tool_result" in kinds  # kb_search ran
    assert "sources" in kinds
    assert kinds[-1] == "done"

    done = next(d for k, d in events if k == "done")
    assert done["status"] == "completed"

    # trace steps were persisted
    async with SessionLocal() as session:
        steps = (
            await session.scalars(
                select(RunStep).where(RunStep.run_id == done["run_id"]).order_by(RunStep.ord)
            )
        ).all()
    types = [s.type for s in steps]
    assert "llm_call" in types
    assert "tool_call" in types


async def test_escalation_is_gated_by_approval_and_resumes(
    client: AsyncClient, db_ready: None
) -> None:
    await _upload_and_wait(client, "kb.txt", b"Billing issues may need a human.")
    conv = (await client.post("/api/v1/conversations", json={})).json()

    events = await _agent(
        client, conv["id"], "Please escalate this billing problem to a human agent"
    )
    kinds = [k for k, _ in events]
    assert "approval_required" in kinds
    # the run paused, not completed
    assert "done" not in kinds

    approval = next(d for k, d in events if k == "approval_required")
    run_id = approval["run_id"]

    # approve
    dec = await client.post(
        f"/api/v1/approvals/{approval['approval_id']}/decision", json={"decision": "approve"}
    )
    assert dec.status_code == 200
    assert dec.json()["status"] == "approved"

    # resume
    async with client.stream("POST", f"/api/v1/runs/{run_id}/resume") as resp:
        resume_events = await _collect(resp)
    rkinds = [k for k, _ in resume_events]
    assert rkinds[-1] == "done"
    assert next(d for k, d in resume_events if k == "done")["status"] == "completed"

    # escalation row was created
    async with SessionLocal() as session:
        escs = (await session.scalars(select(Escalation).where(Escalation.run_id == run_id))).all()
    assert len(escs) >= 1


async def test_rejected_escalation_completes_without_ticket(
    client: AsyncClient, db_ready: None
) -> None:
    await _upload_and_wait(client, "kb.txt", b"Some knowledge.")
    conv = (await client.post("/api/v1/conversations", json={})).json()

    events = await _agent(client, conv["id"], "Please escalate this to a human")
    approval = next(d for k, d in events if k == "approval_required")
    run_id = approval["run_id"]

    await client.post(
        f"/api/v1/approvals/{approval['approval_id']}/decision",
        json={"decision": "reject", "note": "handle it yourself"},
    )
    async with client.stream("POST", f"/api/v1/runs/{run_id}/resume") as resp:
        resume_events = await _collect(resp)

    assert next(d for k, d in resume_events if k == "done")["status"] == "completed"
    async with SessionLocal() as session:
        escs = (await session.scalars(select(Escalation).where(Escalation.run_id == run_id))).all()
    assert len(escs) == 0

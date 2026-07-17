"""Agent runs: streaming tool-using answers with an approval pause/resume."""

import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent.loop import resume_agent_run, start_agent_run
from app.db import SessionLocal, get_session
from app.deps import get_workspace_id
from app.models import Conversation, Message, Run
from app.schemas.agent import AgentAskRequest

router = APIRouter(prefix="/api/v1", tags=["agent"])

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def _sse(event: dict) -> str:
    return f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"


async def _finalize_assistant_message(run_id: uuid.UUID) -> None:
    """After a run completes, record its answer as an assistant message (once)."""
    async with SessionLocal() as session:
        run = await session.get(Run, run_id)
        if run is None or run.status != "completed":
            return
        existing = await session.scalar(
            select(Message).where(Message.run_id == run_id, Message.role == "assistant")
        )
        if existing is None:
            session.add(
                Message(
                    conversation_id=run.conversation_id,
                    role="assistant",
                    content=run.answer or "",
                    run_id=run_id,
                )
            )
            await session.commit()


@router.post("/conversations/{conversation_id}/agent")
async def agent_ask(
    conversation_id: uuid.UUID,
    body: AgentAskRequest,
    session: AsyncSession = Depends(get_session),
    workspace_id: uuid.UUID = Depends(get_workspace_id),
) -> StreamingResponse:
    conv = await session.get(Conversation, conversation_id)
    if conv is None or conv.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    run = Run(
        conversation_id=conversation_id, question=body.question, mode="agent", status="running"
    )
    session.add(run)
    session.add(Message(conversation_id=conversation_id, role="user", content=body.question))
    if conv.title is None:
        conv.title = body.question[:80]
    await session.commit()
    await session.refresh(run)
    run_id = run.id

    async def stream() -> AsyncIterator[str]:
        # Give the client the run id up front so it can resume after an approval.
        yield _sse(
            {
                "event": "run",
                "data": {"run_id": str(run_id), "conversation_id": str(conversation_id)},
            }
        )
        async for event in start_agent_run(run_id, workspace_id):
            yield _sse(event)
        await _finalize_assistant_message(run_id)

    return StreamingResponse(stream(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/runs/{run_id}/resume")
async def resume_run(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    workspace_id: uuid.UUID = Depends(get_workspace_id),
) -> StreamingResponse:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    conv = await session.get(Conversation, run.conversation_id)
    if conv is None or conv.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Run not found")

    async def stream() -> AsyncIterator[str]:
        async for event in resume_agent_run(run_id, workspace_id):
            yield _sse(event)
        await _finalize_assistant_message(run_id)

    return StreamingResponse(stream(), media_type="text/event-stream", headers=_SSE_HEADERS)

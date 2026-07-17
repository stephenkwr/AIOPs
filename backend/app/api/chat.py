"""Conversations, streaming Q&A, and run retrieval."""

import json
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.answer import build_messages, citations_payload, compute_confidence
from app.core.llm.base import LLMUsage
from app.core.llm.factory import get_answer_client
from app.core.llm.pricing import estimate_cost
from app.core.retrieval.retriever import retrieve
from app.db import SessionLocal, get_session
from app.deps import get_workspace_id
from app.models import Conversation, Message, Run
from app.schemas.chat import (
    AskRequest,
    ConversationCreate,
    ConversationDetail,
    ConversationOut,
    RunOut,
)

router = APIRouter(prefix="/api/v1", tags=["chat"])

ANSWER_MAX_TOKENS = 1024


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/conversations", response_model=ConversationOut, status_code=201)
async def create_conversation(
    body: ConversationCreate,
    session: AsyncSession = Depends(get_session),
    workspace_id: uuid.UUID = Depends(get_workspace_id),
) -> Conversation:
    conv = Conversation(workspace_id=workspace_id, title=body.title)
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    return conv


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    workspace_id: uuid.UUID = Depends(get_workspace_id),
) -> Conversation:
    conv = await session.get(Conversation, conversation_id)
    if conv is None or conv.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await session.refresh(conv, attribute_names=["messages"])
    return conv


@router.get("/runs/{run_id}", response_model=RunOut)
async def get_run(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    workspace_id: uuid.UUID = Depends(get_workspace_id),
) -> Run:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    conv = await session.get(Conversation, run.conversation_id)
    if conv is None or conv.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/conversations/{conversation_id}/ask")
async def ask(
    conversation_id: uuid.UUID,
    body: AskRequest,
    session: AsyncSession = Depends(get_session),
    workspace_id: uuid.UUID = Depends(get_workspace_id),
) -> StreamingResponse:
    conv = await session.get(Conversation, conversation_id)
    if conv is None or conv.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Create the run + user message up front so the work is durable even if the
    # client disconnects mid-stream.
    run = Run(
        conversation_id=conversation_id, question=body.question, mode=body.mode, status="running"
    )
    session.add(run)
    session.add(Message(conversation_id=conversation_id, role="user", content=body.question))
    if conv.title is None:
        conv.title = body.question[:80]
    await session.commit()
    await session.refresh(run)
    run_id = run.id

    # Retrieve context now (uses the request session).
    retrieved = await retrieve(
        session,
        workspace_id,
        body.question,
        mode=settings.retrieval_mode,
        k=settings.retrieval_k,
        candidates=settings.retrieval_candidates,
    )
    citations = citations_payload(retrieved)
    messages = build_messages(body.question, retrieved)
    client = get_answer_client()

    async def event_stream() -> AsyncIterator[str]:
        start = time.monotonic()
        # Send sources first so the UI can render citations before tokens arrive.
        yield _sse("sources", {"citations": citations})

        answer_parts: list[str] = []
        usage = LLMUsage()
        try:
            async for ev in client.stream(messages, max_tokens=ANSWER_MAX_TOKENS):
                if ev.type == "delta":
                    answer_parts.append(ev.text)
                    yield _sse("token", {"text": ev.text})
                elif ev.type == "done" and ev.usage is not None:
                    usage = ev.usage

            answer = "".join(answer_parts).strip()
            # Which provider actually served (fallback chain may have switched).
            model_name = getattr(client, "last_model", None) or client.model
            confidence, parts = compute_confidence(retrieved, answer)
            latency_ms = int((time.monotonic() - start) * 1000)
            cost = estimate_cost(model_name, usage.input_tokens, usage.output_tokens)

            async with SessionLocal() as write:
                r = await write.get(Run, run_id)
                if r is not None:
                    r.answer = answer
                    r.citations = citations
                    r.confidence = confidence
                    r.confidence_parts = parts
                    r.model = model_name
                    r.tokens_in = usage.input_tokens
                    r.tokens_out = usage.output_tokens
                    r.cost_usd = cost
                    r.latency_ms = latency_ms
                    r.status = "completed"
                    r.finished_at = func.now()
                    write.add(
                        Message(
                            conversation_id=conversation_id,
                            role="assistant",
                            content=answer,
                            run_id=run_id,
                        )
                    )
                    await write.commit()

            yield _sse(
                "done",
                {
                    "run_id": str(run_id),
                    "confidence": confidence,
                    "confidence_parts": parts,
                    "model": model_name,
                    "tokens_in": usage.input_tokens,
                    "tokens_out": usage.output_tokens,
                    "cost_usd": cost,
                    "latency_ms": latency_ms,
                },
            )
        except Exception as exc:  # noqa: BLE001 — surface failure to the client + persist it
            async with SessionLocal() as write:
                r = await write.get(Run, run_id)
                if r is not None:
                    r.status = "failed"
                    r.failure_reason = str(exc)[:500]
                    r.finished_at = func.now()
                    await write.commit()
            yield _sse("error", {"message": str(exc)[:300]})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

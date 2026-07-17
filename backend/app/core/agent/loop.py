"""The agent loop: a durable, DB-backed state machine.

    running ─(read-only tool)→ running
    running ─(side-effect tool)→ awaiting_approval ─(approve/reject)→ running → completed
    running ─(budget/error)→ failed

All agent state lives in run.agent_state (the serialized message history), so a
run survives process restarts and any replica can resume it after an approval —
the approval wait may last minutes or days, longer than any worker lives.

Guardrails (hard budgets) live here: max steps, token ceiling, tool timeout +
retries, arg validation, approval expiry. Every failure ends the run cleanly and
hands control back to a human.
"""

import asyncio
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.answer import compute_agent_confidence
from app.core.llm.base import (
    LLMMessage,
    ToolSpec,
    messages_from_dicts,
    messages_to_dicts,
)
from app.core.llm.factory import get_answer_client
from app.core.llm.pricing import estimate_cost
from app.db import SessionLocal
from app.models import Approval, Run, RunStep
from app.tools.base import ToolContext, ToolResult
from app.tools.registry import REGISTRY, tool_specs

AGENT_SYSTEM_PROMPT = (
    "You are a support-resolution copilot for an internal help desk. You have tools:\n"
    "- search_knowledge_base: find answers in internal docs. ALWAYS use this before "
    "answering a factual question, and cite sources inline as [n].\n"
    "- lookup_order: check an order's status by number or customer email.\n"
    "- create_escalation: hand off to a human. This changes state and REQUIRES human "
    "approval before it runs; use it when you can't resolve the issue from the sources.\n"
    "Cite every claim with [n]. Be concise. If the sources don't answer the question, "
    "say so and create an escalation."
)

ANSWER_MAX_TOKENS = 1024


def _now() -> datetime:
    return datetime.now(UTC)


def _validate_args(tool, args: dict) -> None:
    required = tool.parameters.get("required", [])
    missing = [key for key in required if key not in args or args[key] in (None, "")]
    if missing:
        raise ValueError(f"missing required argument(s): {', '.join(missing)}")


async def _execute_with_guardrails(tool, args: dict, ctx: ToolContext) -> ToolResult:
    _validate_args(tool, args)
    last_exc: Exception | None = None
    for _ in range(settings.tool_max_retries + 1):
        try:
            return await asyncio.wait_for(
                tool.execute(args, ctx), timeout=settings.tool_timeout_seconds
            )
        except TimeoutError as exc:  # retry only timeouts
            last_exc = exc
            continue
    raise last_exc if last_exc else RuntimeError("tool failed")


def _done_event(run: Run) -> dict:
    return {
        "event": "done",
        "data": {
            "run_id": str(run.id),
            "status": run.status,
            "confidence": float(run.confidence) if run.confidence is not None else None,
            "confidence_parts": run.confidence_parts,
            "model": run.model,
            "tokens_in": run.tokens_in,
            "tokens_out": run.tokens_out,
            "cost_usd": float(run.cost_usd),
            "latency_ms": run.latency_ms,
        },
    }


async def _next_ord(session: AsyncSession, run_id) -> int:
    count = await session.scalar(
        select(func.count()).select_from(RunStep).where(RunStep.run_id == run_id)
    )
    return int(count or 0)


async def start_agent_run(run_id, workspace_id) -> AsyncIterator[dict]:
    async with SessionLocal() as session:
        run = await session.get(Run, run_id)
        if run is None:
            yield {"event": "error", "data": {"message": "Run not found"}}
            return
        messages = [
            LLMMessage(role="system", content=AGENT_SYSTEM_PROMPT),
            LLMMessage(role="user", content=run.question),
        ]
        run.agent_state = messages_to_dicts(messages)
        run.status = "running"
        await session.commit()
        async for event in _engine(session, run, messages, workspace_id):
            yield event


async def resume_agent_run(run_id, workspace_id) -> AsyncIterator[dict]:
    async with SessionLocal() as session:
        run = await session.get(Run, run_id)
        if run is None:
            yield {"event": "error", "data": {"message": "Run not found"}}
            return
        if run.status != "awaiting_approval":
            yield {"event": "error", "data": {"message": "Run is not awaiting approval"}}
            return

        messages = messages_from_dicts(run.agent_state or [])
        last_assistant = next(
            (m for m in reversed(messages) if m.role == "assistant" and m.tool_calls), None
        )
        if last_assistant is None:
            yield {"event": "error", "data": {"message": "No pending tool calls to resume"}}
            return

        ctx = ToolContext(session=session, workspace_id=workspace_id, run_id=run.id)
        approvals = {
            a.tool_call_id: a
            for a in (
                await session.scalars(select(Approval).where(Approval.run_id == run.id))
            ).all()
        }
        ord_counter = await _next_ord(session, run.id)

        for tc in last_assistant.tool_calls:
            tool = REGISTRY.get(tc.name)
            if tool is None:
                messages.append(
                    LLMMessage(
                        role="tool", tool_call_id=tc.id, name=tc.name, content="Error: unknown tool"
                    )
                )
                continue

            if tool.side_effect:
                approval = approvals.get(tc.id)
                if approval is None or approval.status == "pending":
                    if approval is not None and approval.expires_at < _now():
                        approval.status = "expired"
                        run.status = "cancelled"
                        run.failure_reason = "approval_expired"
                        run.finished_at = func.now()
                        await session.commit()
                        yield {
                            "event": "error",
                            "data": {"message": "Approval expired — run cancelled."},
                        }
                        yield _done_event(run)
                        return
                    yield {"event": "error", "data": {"message": "Approval is still pending."}}
                    return

                ord_counter += 1
                if approval.status == "approved":
                    result = await _execute_with_guardrails(tool, tc.arguments, ctx)
                    session.add(
                        RunStep(
                            run_id=run.id,
                            ord=ord_counter,
                            type="tool_call",
                            name=tc.name,
                            input=tc.arguments,
                            output=result.data,
                            status="ok",
                        )
                    )
                    messages.append(
                        LLMMessage(
                            role="tool", tool_call_id=tc.id, name=tc.name, content=result.content
                        )
                    )
                    yield {
                        "event": "tool_result",
                        "data": {"name": tc.name, "status": "approved", "data": result.data},
                    }
                else:  # rejected
                    note = approval.note or "no reason given"
                    content = (
                        f"The user DECLINED this action. Reason: {note}. "
                        "Do not attempt it again; adapt your response accordingly."
                    )
                    session.add(
                        RunStep(
                            run_id=run.id,
                            ord=ord_counter,
                            type="tool_call",
                            name=tc.name,
                            input=tc.arguments,
                            output={"declined": True, "note": approval.note},
                            status="rejected",
                        )
                    )
                    messages.append(
                        LLMMessage(role="tool", tool_call_id=tc.id, name=tc.name, content=content)
                    )
                    yield {"event": "tool_result", "data": {"name": tc.name, "status": "rejected"}}
            else:
                # read-only sibling deferred from the paused turn
                ord_counter += 1
                result = await _execute_with_guardrails(tool, tc.arguments, ctx)
                session.add(
                    RunStep(
                        run_id=run.id,
                        ord=ord_counter,
                        type="tool_call",
                        name=tc.name,
                        input=tc.arguments,
                        output=result.data,
                        status="ok",
                    )
                )
                messages.append(
                    LLMMessage(
                        role="tool", tool_call_id=tc.id, name=tc.name, content=result.content
                    )
                )
                if result.citations:
                    run.citations = result.citations
                    yield {"event": "sources", "data": {"citations": result.citations}}
                yield {
                    "event": "tool_result",
                    "data": {"name": tc.name, "status": "ok", "data": result.data},
                }

        run.status = "running"
        run.agent_state = messages_to_dicts(messages)
        await session.commit()

        async for event in _engine(session, run, messages, workspace_id):
            yield event


async def _engine(
    session: AsyncSession, run: Run, messages: list[LLMMessage], workspace_id
) -> AsyncIterator[dict]:
    ctx = ToolContext(session=session, workspace_id=workspace_id, run_id=run.id)
    specs: list[ToolSpec] = tool_specs()
    client = get_answer_client()
    citations: list[dict] = run.citations or []
    ord_counter = await _next_ord(session, run.id)

    while True:
        if run.step_count >= settings.agent_max_steps:
            run.status = "failed"
            run.failure_reason = "step_budget_exceeded"
            run.finished_at = func.now()
            await session.commit()
            yield {
                "event": "error",
                "data": {"message": "Step budget exceeded — handing back to a human."},
            }
            yield _done_event(run)
            return

        t0 = time.monotonic()
        try:
            turn = await client.complete_with_tools(messages, specs, max_tokens=ANSWER_MAX_TOKENS)
        except Exception as exc:  # noqa: BLE001
            run.status = "failed"
            run.failure_reason = f"llm_error: {exc}"[:500]
            run.finished_at = func.now()
            await session.commit()
            yield {
                "event": "error",
                "data": {"message": "The model is unavailable right now. Please retry."},
            }
            yield _done_event(run)
            return
        latency = int((time.monotonic() - t0) * 1000)

        model_name = getattr(client, "last_model", None) or client.model
        cost = estimate_cost(model_name, turn.usage.input_tokens, turn.usage.output_tokens)
        run.step_count += 1
        run.tokens_in += turn.usage.input_tokens
        run.tokens_out += turn.usage.output_tokens
        run.cost_usd = float(run.cost_usd) + cost
        run.latency_ms = (run.latency_ms or 0) + latency
        run.model = model_name
        ord_counter += 1
        session.add(
            RunStep(
                run_id=run.id,
                ord=ord_counter,
                type="llm_call",
                name=model_name,
                output={
                    "text": turn.text,
                    "tool_calls": [
                        {"name": tc.name, "arguments": tc.arguments} for tc in turn.tool_calls
                    ],
                },
                status="ok",
                latency_ms=latency,
                tokens_in=turn.usage.input_tokens,
                tokens_out=turn.usage.output_tokens,
                cost_usd=cost,
            )
        )
        messages.append(LLMMessage(role="assistant", content=turn.text, tool_calls=turn.tool_calls))
        run.agent_state = messages_to_dicts(messages)
        await session.commit()
        yield {
            "event": "step",
            "data": {
                "type": "llm_call",
                "name": model_name,
                "status": "ok",
                "tokens_in": turn.usage.input_tokens,
                "tokens_out": turn.usage.output_tokens,
                "latency_ms": latency,
            },
        }

        if run.tokens_in + run.tokens_out > settings.agent_token_budget:
            run.status = "failed"
            run.failure_reason = "token_budget_exceeded"
            run.finished_at = func.now()
            await session.commit()
            yield {
                "event": "error",
                "data": {"message": "Token budget exceeded — handing back to a human."},
            }
            yield _done_event(run)
            return

        if not turn.tool_calls:
            answer = turn.text.strip()
            confidence, parts = compute_agent_confidence(citations, answer)
            run.answer = answer
            run.citations = citations
            run.confidence = confidence
            run.confidence_parts = parts
            run.status = "completed"
            run.finished_at = func.now()
            await session.commit()
            for word in answer.split(" "):
                yield {"event": "token", "data": {"text": word + " "}}
            yield _done_event(run)
            return

        unknown = [tc for tc in turn.tool_calls if tc.name not in REGISTRY]
        if unknown:
            for tc in unknown:
                messages.append(
                    LLMMessage(
                        role="tool",
                        tool_call_id=tc.id,
                        name=tc.name,
                        content=f"Error: unknown tool {tc.name}",
                    )
                )
            run.agent_state = messages_to_dicts(messages)
            await session.commit()
            continue

        side_effect_calls = [tc for tc in turn.tool_calls if REGISTRY[tc.name].side_effect]

        if side_effect_calls:
            # Pause the whole turn: create an approval per side-effect call.
            emitted = []
            for tc in side_effect_calls:
                ord_counter += 1
                step = RunStep(
                    run_id=run.id,
                    ord=ord_counter,
                    type="approval_wait",
                    name=tc.name,
                    input=tc.arguments,
                    status="pending",
                )
                session.add(step)
                await session.flush()
                approval = Approval(
                    run_id=run.id,
                    step_id=step.id,
                    tool_name=tc.name,
                    tool_args=tc.arguments,
                    tool_call_id=tc.id,
                    status="pending",
                    expires_at=_now() + timedelta(hours=settings.approval_expiry_hours),
                )
                session.add(approval)
                await session.flush()
                emitted.append(
                    {
                        "approval_id": str(approval.id),
                        "run_id": str(run.id),
                        "tool_name": tc.name,
                        "tool_args": tc.arguments,
                        "expires_at": approval.expires_at.isoformat(),
                    }
                )
            run.status = "awaiting_approval"
            run.agent_state = messages_to_dicts(messages)
            await session.commit()
            for data in emitted:
                yield {"event": "approval_required", "data": data}
            return  # pause until resume

        # All read-only: execute now.
        for tc in turn.tool_calls:
            tool = REGISTRY[tc.name]
            t1 = time.monotonic()
            try:
                result = await _execute_with_guardrails(tool, tc.arguments, ctx)
                status = "ok"
            except Exception as exc:  # noqa: BLE001 — feed the error back to the model
                result = ToolResult(content=f"Tool error: {exc}", data={"error": str(exc)})
                status = "error"
            lat = int((time.monotonic() - t1) * 1000)
            run.latency_ms = (run.latency_ms or 0) + lat
            ord_counter += 1
            session.add(
                RunStep(
                    run_id=run.id,
                    ord=ord_counter,
                    type="tool_call",
                    name=tc.name,
                    input=tc.arguments,
                    output=result.data,
                    status=status,
                    latency_ms=lat,
                )
            )
            messages.append(
                LLMMessage(role="tool", tool_call_id=tc.id, name=tc.name, content=result.content)
            )
            if result.citations:
                citations = result.citations
                run.citations = citations
                yield {"event": "sources", "data": {"citations": citations}}
            run.agent_state = messages_to_dicts(messages)
            await session.commit()
            yield {
                "event": "tool_result",
                "data": {"name": tc.name, "status": status, "data": result.data},
            }

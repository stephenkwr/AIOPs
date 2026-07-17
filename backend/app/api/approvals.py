"""Human approval decisions for gated tool calls."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_workspace_id
from app.models import Approval, Conversation, Run
from app.schemas.agent import ApprovalDecision, ApprovalOut

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])


async def _approval_in_workspace(
    session: AsyncSession, approval_id: uuid.UUID, workspace_id: uuid.UUID
) -> Approval:
    approval = await session.get(Approval, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    run = await session.get(Run, approval.run_id)
    conv = await session.get(Conversation, run.conversation_id) if run else None
    if conv is None or conv.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Approval not found")
    return approval


@router.get("", response_model=list[ApprovalOut])
async def list_approvals(
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
    workspace_id: uuid.UUID = Depends(get_workspace_id),
) -> list[Approval]:
    stmt = (
        select(Approval)
        .join(Run, Run.id == Approval.run_id)
        .join(Conversation, Conversation.id == Run.conversation_id)
        .where(Conversation.workspace_id == workspace_id)
        .order_by(Approval.created_at.desc())
    )
    if status:
        stmt = stmt.where(Approval.status == status)
    rows = await session.scalars(stmt)
    return list(rows)


@router.post("/{approval_id}/decision", response_model=ApprovalOut)
async def decide_approval(
    approval_id: uuid.UUID,
    body: ApprovalDecision,
    session: AsyncSession = Depends(get_session),
    workspace_id: uuid.UUID = Depends(get_workspace_id),
) -> Approval:
    approval = await _approval_in_workspace(session, approval_id, workspace_id)

    if approval.status != "pending":
        raise HTTPException(status_code=409, detail=f"Approval already {approval.status}")

    if approval.expires_at < datetime.now(UTC):
        approval.status = "expired"
        await session.commit()
        raise HTTPException(status_code=409, detail="Approval expired")

    approval.status = "approved" if body.decision == "approve" else "rejected"
    approval.decided_at = func.now()
    approval.decided_by = "demo-agent"
    approval.note = body.note
    await session.commit()
    await session.refresh(approval)
    return approval

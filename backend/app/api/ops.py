"""Read-only ops surfaces: orders (mock ERP) and escalations."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_workspace_id
from app.models import Escalation, Order
from app.schemas.agent import EscalationOut, OrderOut

router = APIRouter(prefix="/api/v1", tags=["ops"])


@router.get("/orders", response_model=list[OrderOut])
async def list_orders(
    session: AsyncSession = Depends(get_session),
    workspace_id: uuid.UUID = Depends(get_workspace_id),
) -> list[Order]:
    rows = await session.scalars(
        select(Order).where(Order.workspace_id == workspace_id).order_by(Order.order_number)
    )
    return list(rows)


@router.get("/orders/{order_number}", response_model=OrderOut)
async def get_order(
    order_number: str,
    session: AsyncSession = Depends(get_session),
    workspace_id: uuid.UUID = Depends(get_workspace_id),
) -> Order:
    order = await session.scalar(
        select(Order).where(Order.workspace_id == workspace_id, Order.order_number == order_number)
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.get("/escalations", response_model=list[EscalationOut])
async def list_escalations(
    session: AsyncSession = Depends(get_session),
    workspace_id: uuid.UUID = Depends(get_workspace_id),
) -> list[Escalation]:
    rows = await session.scalars(
        select(Escalation)
        .where(Escalation.workspace_id == workspace_id)
        .order_by(Escalation.created_at.desc())
    )
    return list(rows)

"""Agent, approval, and ops (orders/escalations) API models."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class ApprovalDecision(BaseModel):
    decision: Literal["approve", "reject"]
    note: str | None = None


class ApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    tool_name: str
    tool_args: dict
    status: str
    note: str | None
    decided_at: datetime | None
    expires_at: datetime
    created_at: datetime


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_number: str
    customer_email: str
    status: str
    items: list
    total_usd: float
    created_at: datetime


class EscalationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID | None
    order_id: uuid.UUID | None
    priority: str
    summary: str
    status: str
    created_at: datetime

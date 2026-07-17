"""Chat / conversation / run API models."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    title: str | None = None


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    created_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    run_id: uuid.UUID | None
    created_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    mode: str = "ask"


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    question: str
    mode: str
    status: str
    answer: str | None
    citations: list[dict] | None
    confidence: float | None
    confidence_parts: dict | None
    model: str | None
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int | None
    failure_reason: str | None
    created_at: datetime
    finished_at: datetime | None


class RunSummary(BaseModel):
    """Lean row for the Traces list — no answer/citations payload."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    question: str
    mode: str
    status: str
    model: str | None
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int | None
    confidence: float | None
    step_count: int
    created_at: datetime
    finished_at: datetime | None


class RunStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ord: int
    type: str
    name: str
    input: dict | None
    output: dict | None
    status: str
    latency_ms: int | None
    tokens_in: int
    tokens_out: int
    cost_usd: float
    created_at: datetime


class RunTrace(RunOut):
    """Full run detail plus its ordered step-by-step trace."""

    steps: list[RunStepOut]

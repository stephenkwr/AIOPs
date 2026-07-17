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

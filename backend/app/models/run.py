"""Run: one question → answer cycle.

In Phase 2 a run is a single retrieve-and-answer pass. Phase 3 grows it into the
tool-using agent loop (run_steps, approvals) — the columns here already anticipate
that (status, failure_reason, usage/cost), so the table extends rather than churns.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

RUN_STATUSES = ("running", "awaiting_approval", "completed", "failed", "cancelled")


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running','awaiting_approval','completed','failed','cancelled')",
            name="ck_runs_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, server_default="ask")
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="running")

    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    confidence_parts: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cost_usd: Mapped[float] = mapped_column(Numeric, nullable=False, server_default="0")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Durable agent state: the serialized LLM message history. The run resumes
    # from this after an approval pause, so no agent state lives in memory.
    agent_state: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    step_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

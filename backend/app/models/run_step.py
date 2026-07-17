"""RunStep: one recorded step in a run — the trace (Phase 4 reads these)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

STEP_TYPES = ("retrieval", "llm_call", "tool_call", "approval_wait")


class RunStep(Base):
    __tablename__ = "run_steps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ord: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="ok")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cost_usd: Mapped[float] = mapped_column(Numeric, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

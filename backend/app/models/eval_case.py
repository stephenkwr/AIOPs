"""EvalCase: one dataset question scored within an EvalRun (the per-question trace)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
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


class EvalCase(Base):
    __tablename__ = "eval_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    eval_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("eval_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    case_id: Mapped[str] = mapped_column(String(64), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    answerable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    gold_doc: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Retrieval outcome (retrieved = top-k filenames in order; rank = 1-based first gold hit)
    retrieved: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    hit: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reciprocal_rank: Mapped[float] = mapped_column(Numeric, nullable=False, server_default="0")

    # Answer outcome (judge = {groundedness, correctness, reasoning}; correct = overall pass)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    refused: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    judge: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

"""EvalRun: one execution of the golden dataset under a specific configuration.

Two runs (e.g. keyword-only vs hybrid retrieval) are compared side-by-side to show
the before/after lift in retrieval and answer quality.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

EVAL_STATUSES = ("running", "completed", "failed")


class EvalRun(Base):
    __tablename__ = "eval_runs"
    __table_args__ = (
        CheckConstraint("status IN ('running','completed','failed')", name="ck_eval_runs_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    dataset: Mapped[str] = mapped_column(String(64), nullable=False)
    retrieval_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    k: Mapped[int] = mapped_column(Integer, nullable=False, server_default="8")
    graded: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    answer_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    judge_model: Mapped[str | None] = mapped_column(String(64), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="running")
    num_cases: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # Aggregate metrics: hit@k, mrr, groundedness, correctness, refusal_accuracy, …
    metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

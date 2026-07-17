"""Approval: the human-in-the-loop gate for a side-effecting tool call.

Immutable after a decision — together with run_steps this is the audit trail.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

APPROVAL_STATUSES = ("pending", "approved", "rejected", "expired")


class Approval(Base):
    __tablename__ = "approvals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected','expired')", name="ck_approvals_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    step_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("run_steps.id", ondelete="SET NULL"), nullable=True
    )
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    tool_args: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    tool_call_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    decided_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

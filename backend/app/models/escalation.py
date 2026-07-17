"""Escalation: a ticket created by the agent (after human approval)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("runs.id", ondelete="SET NULL"), nullable=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    priority: Mapped[str] = mapped_column(String(16), nullable=False, server_default="medium")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

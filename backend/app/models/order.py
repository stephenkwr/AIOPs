"""Order: a mock ERP record the agent can look up (read-only)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("workspace_id", "order_number", name="uq_orders_ws_number"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    order_number: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_email: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    items: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    total_usd: Mapped[float] = mapped_column(Numeric, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

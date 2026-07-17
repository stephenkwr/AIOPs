"""orders, escalations, run_steps, approvals + run agent state

Revision ID: 0004_agent_tools
Revises: 0003_conversations_runs
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_agent_tools"
down_revision: str | None = "0003_conversations_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEMO_WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    # --- extend runs: durable agent state + wider status set ---
    op.add_column("runs", sa.Column("agent_state", postgresql.JSONB(), nullable=True))
    op.add_column("runs", sa.Column("step_count", sa.Integer(), server_default="0", nullable=False))
    # 'awaiting_approval' is 17 chars — widen the column before allowing it.
    op.alter_column("runs", "status", type_=sa.String(length=32))
    op.drop_constraint("ck_runs_status", "runs", type_="check")
    op.create_check_constraint(
        "ck_runs_status",
        "runs",
        "status IN ('running','awaiting_approval','completed','failed','cancelled')",
    )

    # --- orders (mock ERP) ---
    op.create_table(
        "orders",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_number", sa.String(length=64), nullable=False),
        sa.Column("customer_email", sa.String(length=320), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "items", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("total_usd", sa.Numeric(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workspace_id", "order_number", name="uq_orders_ws_number"),
    )
    op.create_index("ix_orders_workspace_id", "orders", ["workspace_id"])

    # --- escalations ---
    op.create_table(
        "escalations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("priority", sa.String(length=16), server_default="medium", nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="open", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_escalations_workspace_id", "escalations", ["workspace_id"])

    # --- run_steps (the trace) ---
    op.create_table(
        "run_steps",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ord", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("input", postgresql.JSONB(), nullable=True),
        sa.Column("output", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="ok", nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), server_default="0", nullable=False),
        sa.Column("tokens_out", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cost_usd", sa.Numeric(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_run_steps_run_id", "run_steps", ["run_id"])

    # --- approvals (human-in-the-loop gate + audit) ---
    op.create_table(
        "approvals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column(
            "tool_args", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("tool_call_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("decided_by", sa.String(length=128), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["step_id"], ["run_steps.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected','expired')", name="ck_approvals_status"
        ),
    )
    op.create_index("ix_approvals_run_id", "approvals", ["run_id"])

    # --- seed a few mock orders for the demo workspace ---
    op.execute(
        f"""
        INSERT INTO orders (workspace_id, order_number, customer_email, status, items, total_usd)
        VALUES
          ('{DEMO_WORKSPACE_ID}', '1042', 'alice@example.com', 'shipped',
           '[{{"sku": "WIDGET-1", "name": "Standing desk", "qty": 1}}]'::jsonb, 349.00),
          ('{DEMO_WORKSPACE_ID}', '1043', 'bob@example.com', 'processing',
           '[{{"sku": "CHAIR-9", "name": "Ergo chair", "qty": 2}}]'::jsonb, 512.50),
          ('{DEMO_WORKSPACE_ID}', '1044', 'carol@example.com', 'delivered',
           '[{{"sku": "LAMP-3", "name": "Desk lamp", "qty": 1}}]'::jsonb, 39.99)
        ON CONFLICT (workspace_id, order_number) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("approvals")
    op.drop_table("run_steps")
    op.drop_table("escalations")
    op.drop_table("orders")
    op.drop_constraint("ck_runs_status", "runs", type_="check")
    op.create_check_constraint(
        "ck_runs_status", "runs", "status IN ('running','completed','failed')"
    )
    op.alter_column("runs", "status", type_=sa.String(length=16))
    op.drop_column("runs", "step_count")
    op.drop_column("runs", "agent_state")

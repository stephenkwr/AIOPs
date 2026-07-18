"""eval_runs + eval_cases + seeded eval workspace

Revision ID: 0005_eval
Revises: 0004_agent_tools
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_eval"
down_revision: str | None = "0004_agent_tools"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EVAL_WORKSPACE_ID = "00000000-0000-0000-0000-000000000002"


def upgrade() -> None:
    # Isolated workspace for the fixed eval corpus.
    op.execute(
        f"INSERT INTO workspaces (id, name) VALUES ('{EVAL_WORKSPACE_ID}', 'eval') "
        "ON CONFLICT (name) DO NOTHING"
    )

    op.create_table(
        "eval_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("dataset", sa.String(length=64), nullable=False),
        sa.Column("retrieval_mode", sa.String(length=16), nullable=False),
        sa.Column("k", sa.Integer(), server_default="8", nullable=False),
        sa.Column("graded", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("answer_model", sa.String(length=64), nullable=True),
        sa.Column("judge_model", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="running", nullable=False),
        sa.Column("num_cases", sa.Integer(), server_default="0", nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('running','completed','failed')", name="ck_eval_runs_status"
        ),
    )

    op.create_table(
        "eval_cases",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("eval_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("answerable", sa.Boolean(), nullable=False),
        sa.Column("gold_doc", sa.String(length=128), nullable=True),
        sa.Column("retrieved", postgresql.JSONB(), nullable=True),
        sa.Column("hit", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("reciprocal_rank", sa.Numeric(), server_default="0", nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("refused", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("judge", postgresql.JSONB(), nullable=True),
        sa.Column("correct", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["eval_run_id"], ["eval_runs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_eval_cases_eval_run_id", "eval_cases", ["eval_run_id"])


def downgrade() -> None:
    op.drop_table("eval_cases")
    op.drop_table("eval_runs")
    op.execute(f"DELETE FROM workspaces WHERE id = '{EVAL_WORKSPACE_ID}'")

"""baseline: pgvector extension + workspaces table + demo seed

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Stable id so seeds, tests, and the demo UI can reference the workspace.
DEMO_WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "workspaces",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("name", name="uq_workspaces_name"),
    )

    op.execute(
        f"INSERT INTO workspaces (id, name) VALUES ('{DEMO_WORKSPACE_ID}', 'demo') "
        "ON CONFLICT (name) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("workspaces")
    op.execute("DROP EXTENSION IF EXISTS vector")

"""knowledge v1.3 evaluation principal_snapshot

Revision ID: b4d8e1c27a90
Revises: c7e4b1a90d2f
Create Date: 2026-08-09 15:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b4d8e1c27a90"
down_revision: str | None = "c7e4b1a90d2f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_evaluation_runs",
        sa.Column("principal_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_evaluation_runs", "principal_snapshot")

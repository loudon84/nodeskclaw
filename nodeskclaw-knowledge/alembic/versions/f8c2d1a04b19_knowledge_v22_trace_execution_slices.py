"""knowledge v2.2 retrieval trace execution_slices

Revision ID: f8c2d1a04b19
Revises: e6f1b4c25d37
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f8c2d1a04b19"
down_revision: str | None = "e6f1b4c25d37"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_retrieval_traces",
        sa.Column("execution_slices", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_retrieval_traces", "execution_slices")

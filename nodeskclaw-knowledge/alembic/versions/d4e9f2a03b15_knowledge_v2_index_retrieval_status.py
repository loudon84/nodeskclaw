"""knowledge_v2_index_retrieval_status

Revision ID: d4e9f2a03b15
Revises: c3d8e1f92a04
Create Date: 2026-08-27 12:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e9f2a03b15"
down_revision: str | None = "c3d8e1f92a04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_index_states",
        sa.Column("retrieval_status", sa.String(length=32), nullable=False, server_default="unavailable"),
    )


def downgrade() -> None:
    op.drop_column("knowledge_index_states", "retrieval_status")

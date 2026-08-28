"""knowledge_v23_index_state_input_manifest

Revision ID: b3e7f1a92c04
Revises: a1c9e4f72b08
Create Date: 2026-08-27 23:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b3e7f1a92c04"
down_revision: str | None = "a1c9e4f72b08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_index_states",
        sa.Column("input_manifest_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "knowledge_index_states",
        sa.Column("input_manifest_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_index_states", "input_manifest_summary")
    op.drop_column("knowledge_index_states", "input_manifest_hash")

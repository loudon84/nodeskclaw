"""knowledge_v2_runtime_capability_probe

Revision ID: c3d8e1f92a04
Revises: 91f68d6d4364
Create Date: 2026-08-27 12:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d8e1f92a04"
down_revision: str | None = "91f68d6d4364"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_runtime_bindings",
        sa.Column("last_capability_probe_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "knowledge_runtime_bindings",
        sa.Column("last_capability_probe_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_runtime_bindings", "last_capability_probe_error")
    op.drop_column("knowledge_runtime_bindings", "last_capability_probe_at")

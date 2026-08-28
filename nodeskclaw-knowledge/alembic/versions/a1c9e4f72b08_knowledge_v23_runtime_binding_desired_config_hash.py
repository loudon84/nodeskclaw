"""knowledge_v23_runtime_binding_desired_config_hash

Revision ID: a1c9e4f72b08
Revises: d7a2b9c41e03
Create Date: 2026-08-27 22:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c9e4f72b08"
down_revision: str | None = "d7a2b9c41e03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_runtime_bindings",
        sa.Column("desired_config_hash", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_runtime_bindings", "desired_config_hash")

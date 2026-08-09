"""knowledge v1.3 job leasing v2 fields

Revision ID: c9f2a8b14e31
Revises: b4d8e1c27a90
Create Date: 2026-08-09 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9f2a8b14e31"
down_revision: str | None = "b4d8e1c27a90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("knowledge_ingestion_jobs", sa.Column("lease_token", sa.String(length=64), nullable=True))
    op.add_column(
        "knowledge_ingestion_jobs",
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("knowledge_evaluation_runs", sa.Column("lease_token", sa.String(length=64), nullable=True))
    op.add_column(
        "knowledge_evaluation_runs",
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_evaluation_runs", "last_heartbeat_at")
    op.drop_column("knowledge_evaluation_runs", "lease_token")
    op.drop_column("knowledge_ingestion_jobs", "last_heartbeat_at")
    op.drop_column("knowledge_ingestion_jobs", "lease_token")

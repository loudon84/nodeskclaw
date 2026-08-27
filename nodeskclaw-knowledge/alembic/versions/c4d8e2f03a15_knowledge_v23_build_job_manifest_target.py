"""knowledge_v23_build_job_manifest_target

Revision ID: c4d8e2f03a15
Revises: b3e7f1a92c04
Create Date: 2026-08-27 23:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4d8e2f03a15"
down_revision: str | None = "b3e7f1a92c04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_build_jobs",
        sa.Column("target_kind", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "knowledge_build_jobs",
        sa.Column("target_key", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "knowledge_build_jobs",
        sa.Column("input_manifest_hash", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_build_jobs", "input_manifest_hash")
    op.drop_column("knowledge_build_jobs", "target_key")
    op.drop_column("knowledge_build_jobs", "target_kind")

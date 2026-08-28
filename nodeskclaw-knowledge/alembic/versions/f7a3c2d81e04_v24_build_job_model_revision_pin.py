"""v24 build job model revision pin

Revision ID: f7a3c2d81e04
Revises: e6f7a8b91c02
Create Date: 2026-08-28 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7a3c2d81e04"
down_revision: str | None = "e6f7a8b91c02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_build_jobs",
        sa.Column("knowledge_model_revision_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "knowledge_build_jobs",
        sa.Column("release_candidate_id", sa.String(length=36), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_build_jobs", "release_candidate_id")
    op.drop_column("knowledge_build_jobs", "knowledge_model_revision_id")

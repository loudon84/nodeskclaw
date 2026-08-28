"""v24 knowledge model single active revision

Revision ID: a8b4d1e92f05
Revises: f7a3c2d81e04
Create Date: 2026-08-28 12:05:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a8b4d1e92f05"
down_revision: str | None = "f7a3c2d81e04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_knowledge_model_revision_single_active",
        "knowledge_model_revisions",
        ["knowledge_model_id"],
        unique=True,
        postgresql_where="deleted_at IS NULL AND status = 'active'",
    )


def downgrade() -> None:
    op.drop_index(
        "uq_knowledge_model_revision_single_active",
        table_name="knowledge_model_revisions",
    )

"""knowledge_v244_c04_evaluation

Revision ID: 855b15b37ccf
Revises: 0e3836519746
Create Date: 2026-09-11 17:54:56.193574

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "855b15b37ccf"
down_revision: str | None = "0e3836519746"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "knowledge_evaluation_runs",
        "retrieval_profile_id",
        existing_type=sa.VARCHAR(length=36),
        nullable=True,
    )
    op.add_column(
        "knowledge_evaluation_sets",
        sa.Column("application_id", sa.String(length=36), nullable=True),
    )
    op.alter_column(
        "knowledge_evaluation_sets",
        "knowledge_set_id",
        existing_type=sa.VARCHAR(length=36),
        nullable=True,
    )
    op.create_index(
        op.f("ix_knowledge_evaluation_sets_application_id"),
        "knowledge_evaluation_sets",
        ["application_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_knowledge_evaluation_sets_application_id"),
        table_name="knowledge_evaluation_sets",
    )
    op.alter_column(
        "knowledge_evaluation_sets",
        "knowledge_set_id",
        existing_type=sa.VARCHAR(length=36),
        nullable=False,
    )
    op.drop_column("knowledge_evaluation_sets", "application_id")
    op.alter_column(
        "knowledge_evaluation_runs",
        "retrieval_profile_id",
        existing_type=sa.VARCHAR(length=36),
        nullable=False,
    )

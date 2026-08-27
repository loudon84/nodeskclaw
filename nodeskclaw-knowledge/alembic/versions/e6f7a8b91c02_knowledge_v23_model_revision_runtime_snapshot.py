"""knowledge_v23_model_revision_runtime_snapshot

Revision ID: e6f7a8b91c02
Revises: d5e9f3a14b26
Create Date: 2026-08-27 23:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e6f7a8b91c02"
down_revision: str | None = "d5e9f3a14b26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_model_revisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_model_id", sa.String(length=36), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("entities", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("relations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("terms", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("extraction_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by_member_id", sa.String(length=36), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_model_revisions_deleted_at", "knowledge_model_revisions", ["deleted_at"])
    op.create_index("ix_knowledge_model_revisions_org_id", "knowledge_model_revisions", ["org_id"])
    op.create_index(
        "ix_knowledge_model_revisions_knowledge_model_id",
        "knowledge_model_revisions",
        ["knowledge_model_id"],
    )
    op.create_index(
        "uq_knowledge_model_revision_model_version",
        "knowledge_model_revisions",
        ["knowledge_model_id", "revision_number"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.add_column("knowledge_models", sa.Column("active_revision_id", sa.String(length=36), nullable=True))
    op.add_column(
        "knowledge_applications",
        sa.Column("runtime_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_applications", "runtime_snapshot")
    op.drop_column("knowledge_models", "active_revision_id")
    op.drop_index("uq_knowledge_model_revision_model_version", table_name="knowledge_model_revisions")
    op.drop_index("ix_knowledge_model_revisions_knowledge_model_id", table_name="knowledge_model_revisions")
    op.drop_index("ix_knowledge_model_revisions_org_id", table_name="knowledge_model_revisions")
    op.drop_index("ix_knowledge_model_revisions_deleted_at", table_name="knowledge_model_revisions")
    op.drop_table("knowledge_model_revisions")

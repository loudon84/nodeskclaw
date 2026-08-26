"""knowledge_v2_model_chat_application

Revision ID: a4f5dc5166ab
Revises: 4beff359ce9a
Create Date: 2026-08-26 16:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a4f5dc5166ab"
down_revision: str | None = "4beff359ce9a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_models",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("entities", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("relations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("terms", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("extraction_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by_member_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_models_org_id", "knowledge_models", ["org_id"])
    op.create_index("ix_knowledge_models_deleted_at", "knowledge_models", ["deleted_at"])
    op.create_index(
        "uq_knowledge_model_org_name",
        "knowledge_models",
        ["org_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.add_column(
        "knowledge_chat_sessions",
        sa.Column("application_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_knowledge_chat_sessions_application_id",
        "knowledge_chat_sessions",
        ["application_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_chat_sessions_application_id", table_name="knowledge_chat_sessions")
    op.drop_column("knowledge_chat_sessions", "application_id")
    op.drop_index("uq_knowledge_model_org_name", table_name="knowledge_models")
    op.drop_index("ix_knowledge_models_deleted_at", table_name="knowledge_models")
    op.drop_index("ix_knowledge_models_org_id", table_name="knowledge_models")
    op.drop_table("knowledge_models")

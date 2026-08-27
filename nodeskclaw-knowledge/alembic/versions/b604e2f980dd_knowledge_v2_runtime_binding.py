"""knowledge_v2_runtime_binding

Revision ID: b604e2f980dd
Revises: e2f5a8b03c16
Create Date: 2026-08-26 15:28:42.858765

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b604e2f980dd"
down_revision: str | None = "e2f5a8b03c16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("knowledge_bases", sa.Column("active_build_profile_id", sa.String(length=36), nullable=True))
    op.add_column("knowledge_bases", sa.Column("knowledge_model_id", sa.String(length=36), nullable=True))
    op.add_column(
        "knowledge_bases",
        sa.Column("build_version", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "knowledge_runtime_bindings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("runtime_type", sa.String(length=32), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=False),
        sa.Column("runtime_version", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ready"),
        sa.Column("capabilities", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("runtime_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_runtime_bindings_org_id", "knowledge_runtime_bindings", ["org_id"])
    op.create_index(
        "ix_knowledge_runtime_bindings_knowledge_base_id",
        "knowledge_runtime_bindings",
        ["knowledge_base_id"],
    )
    op.create_index("ix_knowledge_runtime_bindings_deleted_at", "knowledge_runtime_bindings", ["deleted_at"])
    op.create_index(
        "uq_runtime_binding_kb_type",
        "knowledge_runtime_bindings",
        ["knowledge_base_id", "runtime_type", "resource_type"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_runtime_binding_resource",
        "knowledge_runtime_bindings",
        ["runtime_type", "resource_type", "resource_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_runtime_binding_resource", table_name="knowledge_runtime_bindings")
    op.drop_index("uq_runtime_binding_kb_type", table_name="knowledge_runtime_bindings")
    op.drop_index("ix_knowledge_runtime_bindings_deleted_at", table_name="knowledge_runtime_bindings")
    op.drop_index("ix_knowledge_runtime_bindings_knowledge_base_id", table_name="knowledge_runtime_bindings")
    op.drop_index("ix_knowledge_runtime_bindings_org_id", table_name="knowledge_runtime_bindings")
    op.drop_table("knowledge_runtime_bindings")
    op.drop_column("knowledge_bases", "build_version")
    op.drop_column("knowledge_bases", "knowledge_model_id")
    op.drop_column("knowledge_bases", "active_build_profile_id")

"""knowledge_v23_knowledge_artifact_catalog

Revision ID: d5e9f3a14b26
Revises: c4d8e2f03a15
Create Date: 2026-08-27 23:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d5e9f3a14b26"
down_revision: str | None = "c4d8e2f03a15"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_artifacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("source_file_id", sa.String(length=36), nullable=True),
        sa.Column("file_version_id", sa.String(length=36), nullable=True),
        sa.Column("runtime_binding_id", sa.String(length=36), nullable=True),
        sa.Column("runtime_resource_ref", sa.String(length=256), nullable=True),
        sa.Column("artifact_uri", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("input_manifest_hash", sa.String(length=64), nullable=True),
        sa.Column("lineage_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("validation_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("coverage_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("provider_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_built_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_artifacts_deleted_at", "knowledge_artifacts", ["deleted_at"], unique=False)
    op.create_index("ix_knowledge_artifacts_org_id", "knowledge_artifacts", ["org_id"], unique=False)
    op.create_index("ix_knowledge_artifacts_knowledge_base_id", "knowledge_artifacts", ["knowledge_base_id"], unique=False)
    op.create_index("ix_knowledge_artifacts_artifact_type", "knowledge_artifacts", ["artifact_type"], unique=False)
    op.create_index(
        "uq_knowledge_artifact_kb_type_status",
        "knowledge_artifacts",
        ["org_id", "knowledge_base_id", "artifact_type", "status"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_knowledge_artifact_kb_type_status", table_name="knowledge_artifacts")
    op.drop_index("ix_knowledge_artifacts_artifact_type", table_name="knowledge_artifacts")
    op.drop_index("ix_knowledge_artifacts_knowledge_base_id", table_name="knowledge_artifacts")
    op.drop_index("ix_knowledge_artifacts_org_id", table_name="knowledge_artifacts")
    op.drop_index("ix_knowledge_artifacts_deleted_at", table_name="knowledge_artifacts")
    op.drop_table("knowledge_artifacts")

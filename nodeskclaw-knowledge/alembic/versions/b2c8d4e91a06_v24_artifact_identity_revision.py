"""v24 knowledge artifact identity revision

Revision ID: b2c8d4e91a06
Revises: a8b4d1e92f05
Create Date: 2026-08-28 12:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2c8d4e91a06"
down_revision: str | None = "a8b4d1e92f05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("uq_knowledge_artifact_kb_type_status", table_name="knowledge_artifacts")
    op.add_column(
        "knowledge_artifacts",
        sa.Column("active_revision_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "uq_knowledge_artifact_file_identity",
        "knowledge_artifacts",
        ["org_id", "knowledge_base_id", "artifact_type", "scope", "source_file_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND source_file_id IS NOT NULL"),
    )
    op.create_index(
        "uq_knowledge_artifact_kb_identity",
        "knowledge_artifacts",
        ["org_id", "knowledge_base_id", "artifact_type", "scope"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND source_file_id IS NULL"),
    )
    op.create_table(
        "knowledge_artifact_revisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_artifact_id", sa.String(length=36), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("file_version_id", sa.String(length=36), nullable=True),
        sa.Column("input_manifest_hash", sa.String(length=64), nullable=True),
        sa.Column("artifact_uri", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("validation_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("coverage_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("provider_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("lineage_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_built_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["knowledge_artifact_id"], ["knowledge_artifacts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_knowledge_artifact_revisions_deleted_at",
        "knowledge_artifact_revisions",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_artifact_revisions_org_id",
        "knowledge_artifact_revisions",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_artifact_revisions_knowledge_artifact_id",
        "knowledge_artifact_revisions",
        ["knowledge_artifact_id"],
        unique=False,
    )
    op.create_index(
        "uq_knowledge_artifact_revision_number",
        "knowledge_artifact_revisions",
        ["knowledge_artifact_id", "revision_number"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_knowledge_artifact_revision_single_ready",
        "knowledge_artifact_revisions",
        ["knowledge_artifact_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND status = 'ready'"),
    )


def downgrade() -> None:
    op.drop_index("uq_knowledge_artifact_revision_single_ready", table_name="knowledge_artifact_revisions")
    op.drop_index("uq_knowledge_artifact_revision_number", table_name="knowledge_artifact_revisions")
    op.drop_index("ix_knowledge_artifact_revisions_knowledge_artifact_id", table_name="knowledge_artifact_revisions")
    op.drop_index("ix_knowledge_artifact_revisions_org_id", table_name="knowledge_artifact_revisions")
    op.drop_index("ix_knowledge_artifact_revisions_deleted_at", table_name="knowledge_artifact_revisions")
    op.drop_table("knowledge_artifact_revisions")
    op.drop_index("uq_knowledge_artifact_kb_identity", table_name="knowledge_artifacts")
    op.drop_index("uq_knowledge_artifact_file_identity", table_name="knowledge_artifacts")
    op.drop_column("knowledge_artifacts", "active_revision_id")
    op.create_index(
        "uq_knowledge_artifact_kb_type_status",
        "knowledge_artifacts",
        ["org_id", "knowledge_base_id", "artifact_type", "status"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

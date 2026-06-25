"""v5.6 mcp artifact bridge

Revision ID: d1e97d4d4411
Revises: b7e2f1a94c03
Create Date: 2026-06-26 00:59:24.058953

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d1e97d4d4411"
down_revision: str | Sequence[str] | None = "b7e2f1a94c03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hermes_artifact_kb_ingestion_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("artifact_id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_base", sa.String(length=128), nullable=False, server_default="general"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending_review"),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sha256", sa.String(length=128), nullable=True),
        sa.Column("reviewed_by", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("index_error", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["artifact_id"], ["hermes_artifacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["hermes_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_hermes_artifact_kb_ingestion_jobs_deleted_at"),
        "hermes_artifact_kb_ingestion_jobs",
        ["deleted_at"],
        unique=False,
    )
    op.create_index("ix_hermes_kb_jobs_artifact", "hermes_artifact_kb_ingestion_jobs", ["artifact_id"], unique=False)
    op.create_index("ix_hermes_kb_jobs_org_status", "hermes_artifact_kb_ingestion_jobs", ["org_id", "status"], unique=False)
    op.create_index(
        "ix_hermes_kb_jobs_sha256_org",
        "hermes_artifact_kb_ingestion_jobs",
        ["org_id", "sha256"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL AND sha256 IS NOT NULL"),
    )
    op.create_index("ix_hermes_kb_jobs_task", "hermes_artifact_kb_ingestion_jobs", ["task_id"], unique=False)

    op.add_column("hermes_artifacts", sa.Column("object_key", sa.Text(), nullable=True))
    op.add_column("hermes_artifacts", sa.Column("suggested_workspace_dir", sa.Text(), nullable=True))
    op.add_column("hermes_artifacts", sa.Column("suggested_workspace_path", sa.Text(), nullable=True))
    op.add_column(
        "hermes_artifacts",
        sa.Column("workspace_saved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "hermes_artifacts",
        sa.Column("kb_status", sa.String(length=32), nullable=False, server_default="none"),
    )
    op.add_column("hermes_artifacts", sa.Column("format", sa.String(length=32), nullable=True))
    op.add_column(
        "hermes_artifacts",
        sa.Column("source", sa.String(length=32), nullable=False, server_default="discovery"),
    )

    op.add_column("hermes_skills", sa.Column("output_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    op.add_column("hermes_tasks", sa.Column("output_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("hermes_tasks", sa.Column("server_artifacts", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column(
        "hermes_tasks",
        sa.Column("artifact_status", sa.String(length=32), nullable=False, server_default="none"),
    )
    op.add_column(
        "hermes_tasks",
        sa.Column("kb_status", sa.String(length=32), nullable=False, server_default="none"),
    )


def downgrade() -> None:
    op.drop_column("hermes_tasks", "kb_status")
    op.drop_column("hermes_tasks", "artifact_status")
    op.drop_column("hermes_tasks", "server_artifacts")
    op.drop_column("hermes_tasks", "output_policy")
    op.drop_column("hermes_skills", "output_policy")
    op.drop_column("hermes_artifacts", "source")
    op.drop_column("hermes_artifacts", "format")
    op.drop_column("hermes_artifacts", "kb_status")
    op.drop_column("hermes_artifacts", "workspace_saved")
    op.drop_column("hermes_artifacts", "suggested_workspace_path")
    op.drop_column("hermes_artifacts", "suggested_workspace_dir")
    op.drop_column("hermes_artifacts", "object_key")
    op.drop_index("ix_hermes_kb_jobs_task", table_name="hermes_artifact_kb_ingestion_jobs")
    op.drop_index(
        "ix_hermes_kb_jobs_sha256_org",
        table_name="hermes_artifact_kb_ingestion_jobs",
        postgresql_where=sa.text("deleted_at IS NULL AND sha256 IS NOT NULL"),
    )
    op.drop_index("ix_hermes_kb_jobs_org_status", table_name="hermes_artifact_kb_ingestion_jobs")
    op.drop_index("ix_hermes_kb_jobs_artifact", table_name="hermes_artifact_kb_ingestion_jobs")
    op.drop_index(
        op.f("ix_hermes_artifact_kb_ingestion_jobs_deleted_at"),
        table_name="hermes_artifact_kb_ingestion_jobs",
    )
    op.drop_table("hermes_artifact_kb_ingestion_jobs")

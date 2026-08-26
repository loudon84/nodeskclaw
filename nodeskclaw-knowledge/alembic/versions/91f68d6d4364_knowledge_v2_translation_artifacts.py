"""knowledge_v2_translation_artifacts

Revision ID: 91f68d6d4364
Revises: a4f5dc5166ab
Create Date: 2026-08-26 16:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "91f68d6d4364"
down_revision: str | None = "a4f5dc5166ab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_translation_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("source_file_id", sa.String(length=36), nullable=False),
        sa.Column("file_version_id", sa.String(length=36), nullable=False),
        sa.Column("target_lang", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_member_id", sa.String(length=36), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_translation_documents_org_id", "knowledge_translation_documents", ["org_id"])
    op.create_index(
        "ix_knowledge_translation_documents_source_file_id",
        "knowledge_translation_documents",
        ["source_file_id"],
    )
    op.create_index(
        "ix_knowledge_translation_documents_file_version_id",
        "knowledge_translation_documents",
        ["file_version_id"],
    )
    op.create_index(
        "ix_knowledge_translation_documents_deleted_at",
        "knowledge_translation_documents",
        ["deleted_at"],
    )
    op.create_index(
        "uq_translation_doc_source_lang",
        "knowledge_translation_documents",
        ["source_file_id", "file_version_id", "target_lang"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "knowledge_translation_pages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("current_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("artifact_uri", sa.String(length=512), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_knowledge_translation_pages_document_id",
        "knowledge_translation_pages",
        ["document_id"],
    )
    op.create_index("ix_knowledge_translation_pages_deleted_at", "knowledge_translation_pages", ["deleted_at"])
    op.create_index(
        "uq_translation_page",
        "knowledge_translation_pages",
        ["document_id", "page_no"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "knowledge_translation_revisions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("page_id", sa.String(length=36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("artifact_uri", sa.String(length=512), nullable=True),
        sa.Column("created_by_member_id", sa.String(length=36), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_knowledge_translation_revisions_page_id",
        "knowledge_translation_revisions",
        ["page_id"],
    )
    op.create_index(
        "ix_knowledge_translation_revisions_deleted_at",
        "knowledge_translation_revisions",
        ["deleted_at"],
    )
    op.create_index(
        "uq_translation_revision",
        "knowledge_translation_revisions",
        ["page_id", "revision"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "knowledge_translation_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("page_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_token", sa.String(length=64), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_translation_jobs_org_id", "knowledge_translation_jobs", ["org_id"])
    op.create_index(
        "ix_knowledge_translation_jobs_document_id",
        "knowledge_translation_jobs",
        ["document_id"],
    )
    op.create_index("ix_knowledge_translation_jobs_page_id", "knowledge_translation_jobs", ["page_id"])
    op.create_index("ix_knowledge_translation_jobs_status", "knowledge_translation_jobs", ["status"])
    op.create_index("ix_knowledge_translation_jobs_deleted_at", "knowledge_translation_jobs", ["deleted_at"])


def downgrade() -> None:
    op.drop_table("knowledge_translation_jobs")
    op.drop_table("knowledge_translation_revisions")
    op.drop_table("knowledge_translation_pages")
    op.drop_table("knowledge_translation_documents")

"""Initial knowledge domain tables.

Revision ID: 20260808_knowledge_001
Revises:
Create Date: 2026-08-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260808_knowledge_001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("ragflow_dataset_id", sa.String(length=64), nullable=True),
        sa.Column("embedding_model", sa.String(length=128), nullable=False),
        sa.Column("chunk_method", sa.String(length=64), nullable=False),
        sa.Column("parser_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("owner_member_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_bases_org_id", "knowledge_bases", ["org_id"])
    op.create_index("ix_knowledge_bases_deleted_at", "knowledge_bases", ["deleted_at"])
    op.create_index(
        "uq_kb_org_name",
        "knowledge_bases",
        ["org_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_kb_ragflow_dataset",
        "knowledge_bases",
        ["ragflow_dataset_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND ragflow_dataset_id IS NOT NULL"),
    )

    op.create_table(
        "knowledge_base_acl",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("subject_type", sa.String(length=32), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("permission", sa.String(length=32), nullable=False),
        sa.Column("effect", sa.String(length=16), nullable=False),
        sa.Column("created_by_member_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_base_acl_kb_id", "knowledge_base_acl", ["knowledge_base_id"])
    op.create_index("ix_knowledge_base_acl_deleted_at", "knowledge_base_acl", ["deleted_at"])
    op.create_index(
        "uq_kb_acl",
        "knowledge_base_acl",
        ["knowledge_base_id", "subject_type", "subject_id", "permission"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "source_files",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("file_name", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("owner_member_id", sa.String(length=36), nullable=False),
        sa.Column("active_version_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_source_files_org_id", "source_files", ["org_id"])
    op.create_index("ix_source_files_kb_id", "source_files", ["knowledge_base_id"])
    op.create_index("ix_source_files_deleted_at", "source_files", ["deleted_at"])
    op.create_index(
        "uq_source_file_kb_name",
        "source_files",
        ["knowledge_base_id", "file_name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "source_file_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_file_id", sa.String(length=36), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("ragflow_document_id", sa.String(length=64), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("uploaded_by_member_id", sa.String(length=36), nullable=False),
        sa.Column("ragflow_status", sa.String(length=32), nullable=True),
        sa.Column("parse_status", sa.String(length=32), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_source_file_versions_sf_id", "source_file_versions", ["source_file_id"])
    op.create_index("ix_source_file_versions_deleted_at", "source_file_versions", ["deleted_at"])
    op.create_index(
        "uq_sfv_source_version",
        "source_file_versions",
        ["source_file_id", "version_no"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_sfv_ragflow_document",
        "source_file_versions",
        ["ragflow_document_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND ragflow_document_id IS NOT NULL"),
    )

    op.create_table(
        "source_file_acl",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_file_id", sa.String(length=36), nullable=False),
        sa.Column("subject_type", sa.String(length=32), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("permission", sa.String(length=32), nullable=False),
        sa.Column("effect", sa.String(length=16), nullable=False),
        sa.Column("created_by_member_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_source_file_acl_sf_id", "source_file_acl", ["source_file_id"])
    op.create_index("ix_source_file_acl_deleted_at", "source_file_acl", ["deleted_at"])
    op.create_index(
        "uq_sf_acl",
        "source_file_acl",
        ["source_file_id", "subject_type", "subject_id", "permission"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "knowledge_sets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("embedding_model", sa.String(length=128), nullable=False),
        sa.Column("owner_member_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_sets_org_id", "knowledge_sets", ["org_id"])
    op.create_index("ix_knowledge_sets_deleted_at", "knowledge_sets", ["deleted_at"])
    op.create_index(
        "uq_ks_org_name",
        "knowledge_sets",
        ["org_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "knowledge_set_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("knowledge_set_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("weight", sa.Numeric(8, 4), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_set_items_set_id", "knowledge_set_items", ["knowledge_set_id"])
    op.create_index("ix_knowledge_set_items_kb_id", "knowledge_set_items", ["knowledge_base_id"])
    op.create_index("ix_knowledge_set_items_deleted_at", "knowledge_set_items", ["deleted_at"])
    op.create_index(
        "uq_ks_item",
        "knowledge_set_items",
        ["knowledge_set_id", "knowledge_base_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "knowledge_ingestion_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_file_id", sa.String(length=36), nullable=False),
        sa.Column("file_version_id", sa.String(length=36), nullable=False),
        sa.Column("ragflow_document_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("created_by_member_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ingestion_jobs_sf_id", "knowledge_ingestion_jobs", ["source_file_id"])
    op.create_index("ix_ingestion_jobs_version_id", "knowledge_ingestion_jobs", ["file_version_id"])
    op.create_index("ix_ingestion_jobs_deleted_at", "knowledge_ingestion_jobs", ["deleted_at"])

    op.create_table(
        "retrieval_audits",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("member_id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_set_id", sa.String(length=36), nullable=False),
        sa.Column("query_hash", sa.String(length=64), nullable=False),
        sa.Column("candidate_chunk_count", sa.Integer(), nullable=False),
        sa.Column("filtered_chunk_count", sa.Integer(), nullable=False),
        sa.Column("returned_chunk_count", sa.Integer(), nullable=False),
        sa.Column("source_file_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_retrieval_audits_member_id", "retrieval_audits", ["member_id"])
    op.create_index("ix_retrieval_audits_org_id", "retrieval_audits", ["org_id"])
    op.create_index("ix_retrieval_audits_set_id", "retrieval_audits", ["knowledge_set_id"])
    op.create_index("ix_retrieval_audits_deleted_at", "retrieval_audits", ["deleted_at"])


def downgrade() -> None:
    op.drop_table("retrieval_audits")
    op.drop_table("knowledge_ingestion_jobs")
    op.drop_table("knowledge_set_items")
    op.drop_table("knowledge_sets")
    op.drop_table("source_file_acl")
    op.drop_table("source_file_versions")
    op.drop_table("source_files")
    op.drop_table("knowledge_base_acl")
    op.drop_table("knowledge_bases")

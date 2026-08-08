"""knowledge v1.1 runtime

Revision ID: 1acf2f9a5d24
Revises: 20260808_knowledge_001
Create Date: 2026-08-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "1acf2f9a5d24"
down_revision: Union[str, None] = "20260808_knowledge_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge_bases", sa.Column("acl_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("knowledge_bases", sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("knowledge_bases", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column("knowledge_bases", sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column(
        "knowledge_bases",
        sa.Column("visibility", sa.String(length=32), nullable=False, server_default="private"),
    )

    op.add_column("source_files", sa.Column("acl_version", sa.Integer(), nullable=False, server_default="1"))

    op.add_column("source_file_versions", sa.Column("ragflow_run", sa.String(length=32), nullable=True))
    op.add_column("source_file_versions", sa.Column("ragflow_progress", sa.Float(), nullable=True))
    op.add_column("source_file_versions", sa.Column("ragflow_progress_msg", sa.Text(), nullable=True))
    op.add_column("source_file_versions", sa.Column("chunk_count", sa.Integer(), nullable=True))
    op.add_column("source_file_versions", sa.Column("token_count", sa.Integer(), nullable=True))
    op.add_column("source_file_versions", sa.Column("process_duration", sa.Float(), nullable=True))

    op.add_column("knowledge_sets", sa.Column("acl_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column(
        "knowledge_sets",
        sa.Column(
            "retrieval_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text(
                '\'{"top_k": 1024, "top_n": 8, "similarity_threshold": 0.2, '
                '"vector_similarity_weight": 0.7, "keyword": false, "rerank_id": null, '
                '"highlight": false, "cross_languages": [], "answer_model": ""}\'::jsonb'
            ),
        ),
    )
    op.add_column("knowledge_sets", sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("knowledge_sets", sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column(
        "knowledge_sets",
        sa.Column("visibility", sa.String(length=32), nullable=False, server_default="private"),
    )

    op.add_column(
        "knowledge_ingestion_jobs",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "knowledge_ingestion_jobs",
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
    )
    op.add_column("knowledge_ingestion_jobs", sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("knowledge_ingestion_jobs", sa.Column("lease_owner", sa.String(length=128), nullable=True))
    op.add_column("knowledge_ingestion_jobs", sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "knowledge_ingestion_jobs",
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("knowledge_ingestion_jobs", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column(
        "retrieval_audits",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ok"),
    )
    op.add_column("retrieval_audits", sa.Column("plan_kind", sa.String(length=64), nullable=True))
    op.add_column(
        "retrieval_audits",
        sa.Column("ragflow_call_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("retrieval_audits", sa.Column("error_code", sa.String(length=64), nullable=True))

    op.create_table(
        "knowledge_set_acl",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("knowledge_set_id", sa.String(length=36), nullable=False),
        sa.Column("subject_type", sa.String(length=32), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("permission", sa.String(length=32), nullable=False),
        sa.Column("effect", sa.String(length=16), nullable=False),
        sa.Column("created_by_member_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_set_acl_knowledge_set_id", "knowledge_set_acl", ["knowledge_set_id"])
    op.create_index("ix_knowledge_set_acl_deleted_at", "knowledge_set_acl", ["deleted_at"])
    op.create_index(
        "uq_ks_acl",
        "knowledge_set_acl",
        ["knowledge_set_id", "subject_type", "subject_id", "permission"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "knowledge_chat_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("member_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_set_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=True),
        sa.Column("answer_mode", sa.String(length=32), nullable=False),
        sa.Column("show_citations", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("answer_model", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_chat_sessions_org_id", "knowledge_chat_sessions", ["org_id"])
    op.create_index("ix_knowledge_chat_sessions_member_id", "knowledge_chat_sessions", ["member_id"])
    op.create_index("ix_knowledge_chat_sessions_knowledge_set_id", "knowledge_chat_sessions", ["knowledge_set_id"])
    op.create_index("ix_knowledge_chat_sessions_deleted_at", "knowledge_chat_sessions", ["deleted_at"])
    op.create_index(
        "ix_chat_session_member",
        "knowledge_chat_sessions",
        ["org_id", "member_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "knowledge_chat_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_chat_messages_session_id", "knowledge_chat_messages", ["session_id"])
    op.create_index("ix_knowledge_chat_messages_deleted_at", "knowledge_chat_messages", ["deleted_at"])

    op.create_table(
        "knowledge_chat_citations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("message_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("source_file_id", sa.String(length=36), nullable=False),
        sa.Column("file_version_id", sa.String(length=36), nullable=False),
        sa.Column("ragflow_document_id", sa.String(length=64), nullable=True),
        sa.Column("ragflow_chunk_id", sa.String(length=64), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("positions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_chat_citations_message_id", "knowledge_chat_citations", ["message_id"])
    op.create_index("ix_knowledge_chat_citations_source_file_id", "knowledge_chat_citations", ["source_file_id"])
    op.create_index("ix_knowledge_chat_citations_deleted_at", "knowledge_chat_citations", ["deleted_at"])

    op.create_table(
        "knowledge_audit_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("member_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=36), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_audit_logs_org_id", "knowledge_audit_logs", ["org_id"])
    op.create_index("ix_knowledge_audit_logs_member_id", "knowledge_audit_logs", ["member_id"])
    op.create_index("ix_knowledge_audit_logs_action", "knowledge_audit_logs", ["action"])
    op.create_index("ix_knowledge_audit_logs_resource_id", "knowledge_audit_logs", ["resource_id"])
    op.create_index("ix_knowledge_audit_logs_deleted_at", "knowledge_audit_logs", ["deleted_at"])


def downgrade() -> None:
    op.drop_table("knowledge_audit_logs")
    op.drop_table("knowledge_chat_citations")
    op.drop_table("knowledge_chat_messages")
    op.drop_table("knowledge_chat_sessions")
    op.drop_table("knowledge_set_acl")

    op.drop_column("retrieval_audits", "error_code")
    op.drop_column("retrieval_audits", "ragflow_call_count")
    op.drop_column("retrieval_audits", "plan_kind")
    op.drop_column("retrieval_audits", "status")

    op.drop_column("knowledge_ingestion_jobs", "finished_at")
    op.drop_column("knowledge_ingestion_jobs", "last_polled_at")
    op.drop_column("knowledge_ingestion_jobs", "lease_until")
    op.drop_column("knowledge_ingestion_jobs", "lease_owner")
    op.drop_column("knowledge_ingestion_jobs", "next_run_at")
    op.drop_column("knowledge_ingestion_jobs", "max_attempts")
    op.drop_column("knowledge_ingestion_jobs", "attempt_count")

    op.drop_column("knowledge_sets", "visibility")
    op.drop_column("knowledge_sets", "usage_count")
    op.drop_column("knowledge_sets", "last_used_at")
    op.drop_column("knowledge_sets", "retrieval_config")
    op.drop_column("knowledge_sets", "acl_version")

    op.drop_column("source_file_versions", "process_duration")
    op.drop_column("source_file_versions", "token_count")
    op.drop_column("source_file_versions", "chunk_count")
    op.drop_column("source_file_versions", "ragflow_progress_msg")
    op.drop_column("source_file_versions", "ragflow_progress")
    op.drop_column("source_file_versions", "ragflow_run")

    op.drop_column("source_files", "acl_version")

    op.drop_column("knowledge_bases", "visibility")
    op.drop_column("knowledge_bases", "tags")
    op.drop_column("knowledge_bases", "last_error")
    op.drop_column("knowledge_bases", "last_synced_at")
    op.drop_column("knowledge_bases", "acl_version")

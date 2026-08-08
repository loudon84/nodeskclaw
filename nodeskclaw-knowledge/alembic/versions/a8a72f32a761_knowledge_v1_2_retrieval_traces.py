"""knowledge v1.2 retrieval traces

Revision ID: a8a72f32a761
Revises: 2d31da026f7f
Create Date: 2026-08-08 23:32:18.094105

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a8a72f32a761"
down_revision: str | None = "2d31da026f7f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_retrieval_traces",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("query_hash", sa.String(length=64), nullable=False),
        sa.Column("knowledge_set_id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=True),
        sa.Column("profile_version", sa.Integer(), nullable=True),
        sa.Column("member_id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("slice_results", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("timing", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("filter_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("chunk_traces", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_retrieval_traces_query_hash", "knowledge_retrieval_traces", ["query_hash"])
    op.create_index(
        "ix_knowledge_retrieval_traces_knowledge_set_id",
        "knowledge_retrieval_traces",
        ["knowledge_set_id"],
    )
    op.create_index("ix_knowledge_retrieval_traces_profile_id", "knowledge_retrieval_traces", ["profile_id"])
    op.create_index("ix_knowledge_retrieval_traces_member_id", "knowledge_retrieval_traces", ["member_id"])
    op.create_index("ix_knowledge_retrieval_traces_org_id", "knowledge_retrieval_traces", ["org_id"])
    op.create_index("ix_knowledge_retrieval_traces_deleted_at", "knowledge_retrieval_traces", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_retrieval_traces_deleted_at", table_name="knowledge_retrieval_traces")
    op.drop_index("ix_knowledge_retrieval_traces_org_id", table_name="knowledge_retrieval_traces")
    op.drop_index("ix_knowledge_retrieval_traces_member_id", table_name="knowledge_retrieval_traces")
    op.drop_index("ix_knowledge_retrieval_traces_profile_id", table_name="knowledge_retrieval_traces")
    op.drop_index("ix_knowledge_retrieval_traces_knowledge_set_id", table_name="knowledge_retrieval_traces")
    op.drop_index("ix_knowledge_retrieval_traces_query_hash", table_name="knowledge_retrieval_traces")
    op.drop_table("knowledge_retrieval_traces")

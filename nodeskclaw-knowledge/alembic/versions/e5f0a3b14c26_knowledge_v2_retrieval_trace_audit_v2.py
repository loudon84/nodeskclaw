"""knowledge v2 retrieval trace audit v2 fields

Revision ID: e5f0a3b14c26
Revises: d4e9f2a03b15
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e5f0a3b14c26"
down_revision: str | None = "d4e9f2a03b15"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_retrieval_traces",
        sa.Column("query_type", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "knowledge_retrieval_traces",
        sa.Column("requested_indexes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "knowledge_retrieval_traces",
        sa.Column("effective_indexes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "knowledge_retrieval_traces",
        sa.Column("fallback_used", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "knowledge_retrieval_traces",
        sa.Column("fallback_reason", sa.String(length=128), nullable=True),
    )
    op.add_column("retrieval_audits", sa.Column("query_type", sa.String(length=64), nullable=True))
    op.add_column(
        "retrieval_audits",
        sa.Column("requested_indexes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "retrieval_audits",
        sa.Column("effective_indexes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("retrieval_audits", sa.Column("fallback_used", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("retrieval_audits", "fallback_used")
    op.drop_column("retrieval_audits", "effective_indexes")
    op.drop_column("retrieval_audits", "requested_indexes")
    op.drop_column("retrieval_audits", "query_type")
    op.drop_column("knowledge_retrieval_traces", "fallback_reason")
    op.drop_column("knowledge_retrieval_traces", "fallback_used")
    op.drop_column("knowledge_retrieval_traces", "effective_indexes")
    op.drop_column("knowledge_retrieval_traces", "requested_indexes")
    op.drop_column("knowledge_retrieval_traces", "query_type")

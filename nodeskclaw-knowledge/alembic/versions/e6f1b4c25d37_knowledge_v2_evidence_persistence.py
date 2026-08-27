"""knowledge v2 evidence persistence

Revision ID: e6f1b4c25d37
Revises: e5f0a3b14c26
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e6f1b4c25d37"
down_revision: str | None = "e5f0a3b14c26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "knowledge_chat_citations",
        "message_id",
        existing_type=sa.String(length=36),
        nullable=True,
    )
    op.add_column(
        "knowledge_chat_citations",
        sa.Column("org_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "knowledge_chat_citations",
        sa.Column("issued_member_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "knowledge_chat_citations",
        sa.Column("evidence_type", sa.String(length=64), server_default="chunk", nullable=False),
    )
    op.add_column(
        "knowledge_chat_citations",
        sa.Column("content", sa.Text(), nullable=True),
    )
    op.add_column(
        "knowledge_chat_citations",
        sa.Column("source_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "knowledge_chat_citations",
        sa.Column("runtime_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "knowledge_chat_citations",
        sa.Column("origin", sa.String(length=64), server_default="chat", nullable=False),
    )
    op.execute(
        """
        UPDATE knowledge_chat_citations AS c
        SET org_id = s.org_id,
            issued_member_id = s.member_id,
            evidence_type = 'chunk',
            origin = 'chat',
            content = c.quote,
            source_refs = jsonb_build_array(
                jsonb_build_object(
                    'source_file_id', c.source_file_id,
                    'file_version_id', c.file_version_id,
                    'knowledge_base_id', c.knowledge_base_id
                )
            )
        FROM knowledge_chat_messages AS m
        JOIN knowledge_chat_sessions AS s ON s.id = m.session_id
        WHERE c.message_id = m.id
          AND c.org_id IS NULL
        """
    )
    op.alter_column("knowledge_chat_citations", "org_id", nullable=False)
    op.alter_column("knowledge_chat_citations", "issued_member_id", nullable=False)
    op.create_index("ix_knowledge_chat_citations_org_id", "knowledge_chat_citations", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_chat_citations_org_id", table_name="knowledge_chat_citations")
    op.drop_column("knowledge_chat_citations", "origin")
    op.drop_column("knowledge_chat_citations", "runtime_payload")
    op.drop_column("knowledge_chat_citations", "source_refs")
    op.drop_column("knowledge_chat_citations", "content")
    op.drop_column("knowledge_chat_citations", "evidence_type")
    op.drop_column("knowledge_chat_citations", "issued_member_id")
    op.drop_column("knowledge_chat_citations", "org_id")
    op.alter_column(
        "knowledge_chat_citations",
        "message_id",
        existing_type=sa.String(length=36),
        nullable=False,
    )

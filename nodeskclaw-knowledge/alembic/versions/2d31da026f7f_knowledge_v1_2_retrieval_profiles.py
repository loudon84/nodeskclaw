"""knowledge v1.2 retrieval profiles

Revision ID: 2d31da026f7f
Revises: a8c4e2f91b30
Create Date: 2026-08-08 22:14:25.386404

"""

from collections.abc import Sequence
import json
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "2d31da026f7f"
down_revision: str | None = "a8c4e2f91b30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEFAULT_CONFIG = {
    "top_k": 1024,
    "top_n": 8,
    "similarity_threshold": 0.2,
    "vector_similarity_weight": 0.7,
    "keyword": False,
    "rerank_id": None,
    "highlight": False,
    "cross_languages": [],
    "answer_model": "",
    "failure_policy": "fail_closed",
    "context_max_chunks": 8,
    "context_max_chars": 24000,
}


def upgrade() -> None:
    op.create_table(
        "knowledge_retrieval_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("knowledge_set_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by_member_id", sa.String(length=36), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_knowledge_retrieval_profiles_knowledge_set_id",
        "knowledge_retrieval_profiles",
        ["knowledge_set_id"],
    )
    op.create_index(
        "ix_knowledge_retrieval_profiles_deleted_at",
        "knowledge_retrieval_profiles",
        ["deleted_at"],
    )
    op.create_index(
        "uq_retrieval_profile_set_version",
        "knowledge_retrieval_profiles",
        ["knowledge_set_id", "version"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, owner_member_id, retrieval_config FROM knowledge_sets WHERE deleted_at IS NULL"
        )
    ).mappings().all()
    for row in rows:
        config = row["retrieval_config"] if row["retrieval_config"] else _DEFAULT_CONFIG
        if isinstance(config, str):
            config = json.loads(config)
        merged = dict(_DEFAULT_CONFIG)
        if isinstance(config, dict):
            merged.update(config)
        conn.execute(
            sa.text(
                """
                INSERT INTO knowledge_retrieval_profiles
                    (id, knowledge_set_id, version, config, status, created_by_member_id, activated_at, created_at, updated_at)
                VALUES
                    (:id, :knowledge_set_id, 1, CAST(:config AS jsonb), 'active', :created_by_member_id, now(), now(), now())
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "knowledge_set_id": row["id"],
                "config": json.dumps(merged),
                "created_by_member_id": row["owner_member_id"],
            },
        )


def downgrade() -> None:
    op.drop_index("uq_retrieval_profile_set_version", table_name="knowledge_retrieval_profiles")
    op.drop_index("ix_knowledge_retrieval_profiles_deleted_at", table_name="knowledge_retrieval_profiles")
    op.drop_index(
        "ix_knowledge_retrieval_profiles_knowledge_set_id",
        table_name="knowledge_retrieval_profiles",
    )
    op.drop_table("knowledge_retrieval_profiles")

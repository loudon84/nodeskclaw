"""add member tokens

Revision ID: d0a8a590ba70
Revises: 91713580edeb
Create Date: 2026-09-25 22:53:35.797442

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d0a8a590ba70"
down_revision: str | Sequence[str] | None = "91713580edeb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "member_tokens",
        sa.Column("member_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("token_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("models", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provider_group", sa.String(length=64), nullable=True),
        sa.Column("external_token_id", sa.String(length=128), nullable=True),
        sa.Column("token_name", sa.String(length=128), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("sync_status", sa.String(length=24), nullable=False),
        sa.Column("last_sync_error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["member_id"], ["org_memberships.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_member_tokens_deleted_at"), "member_tokens", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_member_tokens_member_id"), "member_tokens", ["member_id"], unique=False)
    op.create_index("ix_member_tokens_external_token_id", "member_tokens", ["external_token_id"], unique=False)
    op.create_index(
        "uq_member_tokens_member_provider",
        "member_tokens",
        ["member_id", "provider"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_member_tokens_one_default",
        "member_tokens",
        ["member_id"],
        unique=True,
        postgresql_where=sa.text("is_default IS TRUE AND deleted_at IS NULL"),
    )
    op.create_index(
        "uq_member_tokens_new_api_token_name",
        "member_tokens",
        ["provider", sa.text("lower(token_name)")],
        unique=True,
        postgresql_where=sa.text(
            "provider = 'new-api' AND token_name IS NOT NULL AND deleted_at IS NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_member_tokens_new_api_token_name", table_name="member_tokens")
    op.drop_index("uq_member_tokens_one_default", table_name="member_tokens")
    op.drop_index("uq_member_tokens_member_provider", table_name="member_tokens")
    op.drop_index("ix_member_tokens_external_token_id", table_name="member_tokens")
    op.drop_index(op.f("ix_member_tokens_member_id"), table_name="member_tokens")
    op.drop_index(op.f("ix_member_tokens_deleted_at"), table_name="member_tokens")
    op.drop_table("member_tokens")

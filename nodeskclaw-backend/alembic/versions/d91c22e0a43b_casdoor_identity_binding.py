"""casdoor identity binding

Revision ID: d91c22e0a43b
Revises: f17188f8316b
Create Date: 2026-10-12 21:51:32.249181

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "d91c22e0a43b"
down_revision: str | Sequence[str] | None = "f17188f8316b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "identity_binding",
        sa.Column("member_user_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_org", sa.String(length=128), nullable=False),
        sa.Column("provider_user_id", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=256), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["member_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_identity_binding_deleted_at"), "identity_binding", ["deleted_at"], unique=False)
    op.create_index(
        "uq_identity_binding_casdoor_member",
        "identity_binding",
        ["member_user_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND provider = 'casdoor'"),
    )
    op.create_index(
        "uq_identity_binding_provider_subject",
        "identity_binding",
        ["provider", "provider_org", "provider_user_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "oauth_login_transaction",
        sa.Column("state", sa.String(length=128), nullable=False),
        sa.Column("code_verifier", sa.String(length=128), nullable=False),
        sa.Column("return_to", sa.String(length=256), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exchange_code_hash", sa.String(length=64), nullable=True),
        sa.Column("exchange_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exchange_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("member_user_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["member_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_oauth_login_transaction_deleted_at"),
        "oauth_login_transaction",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        "uq_oauth_login_transaction_exchange",
        "oauth_login_transaction",
        ["exchange_code_hash"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND exchange_code_hash IS NOT NULL"),
    )
    op.create_index(
        "uq_oauth_login_transaction_state",
        "oauth_login_transaction",
        ["state"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_oauth_login_transaction_state",
        table_name="oauth_login_transaction",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index(
        "uq_oauth_login_transaction_exchange",
        table_name="oauth_login_transaction",
        postgresql_where=sa.text("deleted_at IS NULL AND exchange_code_hash IS NOT NULL"),
    )
    op.drop_index(op.f("ix_oauth_login_transaction_deleted_at"), table_name="oauth_login_transaction")
    op.drop_table("oauth_login_transaction")
    op.drop_index(
        "uq_identity_binding_provider_subject",
        table_name="identity_binding",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index(
        "uq_identity_binding_casdoor_member",
        table_name="identity_binding",
        postgresql_where=sa.text("deleted_at IS NULL AND provider = 'casdoor'"),
    )
    op.drop_index(op.f("ix_identity_binding_deleted_at"), table_name="identity_binding")
    op.drop_table("identity_binding")

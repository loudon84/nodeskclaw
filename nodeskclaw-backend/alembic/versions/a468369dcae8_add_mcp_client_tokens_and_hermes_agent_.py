"""add mcp client tokens and hermes agent mcp gateway fields

Revision ID: a468369dcae8
Revises: d02510ead853
Create Date: 2026-06-25 17:11:00.433094

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a468369dcae8"
down_revision: str | Sequence[str] | None = "d02510ead853"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_client_tokens",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("token_prefix", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False, server_default="mcp_client"),
        sa.Column("service_account_user_id", sa.String(length=36), nullable=True),
        sa.Column("hermes_agent_id", sa.String(length=36), nullable=True),
        sa.Column("hermes_instance_name", sa.String(length=128), nullable=True),
        sa.Column("profile", sa.String(length=128), nullable=False, server_default="default"),
        sa.Column("workspace_id", sa.String(length=128), nullable=False, server_default="default"),
        sa.Column("scopes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("allowed_tools", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("allowed_skills", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("constraints_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["hermes_agent_id"], ["hermes_agent_instances.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mcp_client_tokens_deleted_at"), "mcp_client_tokens", ["deleted_at"], unique=False)
    op.create_index("ix_mcp_client_tokens_hash", "mcp_client_tokens", ["token_hash"], unique=False)
    op.create_index("ix_mcp_client_tokens_org", "mcp_client_tokens", ["org_id"], unique=False)
    op.create_index("ix_mcp_client_tokens_prefix", "mcp_client_tokens", ["token_prefix"], unique=False)
    op.create_index(
        "uq_mcp_client_tokens_active_agent",
        "mcp_client_tokens",
        ["hermes_agent_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND revoked_at IS NULL"),
    )
    op.add_column(
        "hermes_agent_instances",
        sa.Column("mcp_gateway_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("hermes_agent_instances", sa.Column("mcp_gateway_token_id", sa.String(length=36), nullable=True))
    op.add_column(
        "hermes_agent_instances",
        sa.Column("mcp_gateway_token_prefix", sa.String(length=64), nullable=True),
    )
    op.add_column("hermes_agent_instances", sa.Column("mcp_gateway_url", sa.Text(), nullable=True))
    op.add_column(
        "hermes_agent_instances",
        sa.Column("mcp_gateway_env_synced", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "hermes_agent_instances",
        sa.Column("mcp_gateway_last_authorized_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("hermes_agent_instances", sa.Column("mcp_gateway_last_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("hermes_agent_instances", "mcp_gateway_last_error")
    op.drop_column("hermes_agent_instances", "mcp_gateway_last_authorized_at")
    op.drop_column("hermes_agent_instances", "mcp_gateway_env_synced")
    op.drop_column("hermes_agent_instances", "mcp_gateway_url")
    op.drop_column("hermes_agent_instances", "mcp_gateway_token_prefix")
    op.drop_column("hermes_agent_instances", "mcp_gateway_token_id")
    op.drop_column("hermes_agent_instances", "mcp_gateway_enabled")
    op.drop_index(
        "uq_mcp_client_tokens_active_agent",
        table_name="mcp_client_tokens",
        postgresql_where=sa.text("deleted_at IS NULL AND revoked_at IS NULL"),
    )
    op.drop_index("ix_mcp_client_tokens_prefix", table_name="mcp_client_tokens")
    op.drop_index("ix_mcp_client_tokens_org", table_name="mcp_client_tokens")
    op.drop_index("ix_mcp_client_tokens_hash", table_name="mcp_client_tokens")
    op.drop_index(op.f("ix_mcp_client_tokens_deleted_at"), table_name="mcp_client_tokens")
    op.drop_table("mcp_client_tokens")

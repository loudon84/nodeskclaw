"""add integration account and external action policy

Revision ID: 0eba80d0c9e3
Revises: 3ed1bd9bd334
Create Date: 2026-10-02 10:32:38.141074

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0eba80d0c9e3"
down_revision: str | Sequence[str] | None = "3ed1bd9bd334"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_accounts",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("toolkit_slug", sa.String(length=64), nullable=False),
        sa.Column("provider_user_id", sa.String(length=160), nullable=False),
        sa.Column("connected_account_id", sa.String(length=128), nullable=True),
        sa.Column("auth_config_id", sa.String(length=128), nullable=True),
        sa.Column("alias", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("auth_version", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_integration_accounts_deleted_at"), "integration_accounts", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_integration_accounts_org_id"), "integration_accounts", ["org_id"], unique=False)
    op.create_index(op.f("ix_integration_accounts_user_id"), "integration_accounts", ["user_id"], unique=False)
    op.create_index(
        "uq_integration_accounts_owner_provider_account",
        "integration_accounts",
        ["org_id", "user_id", "provider", "connected_account_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "expert_external_action_policies",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("expert_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("toolkit_slug", sa.String(length=64), nullable=False),
        sa.Column("provider_tool_key", sa.String(length=128), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("input_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["expert_id"], ["experts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_expert_external_action_policies_deleted_at"), "expert_external_action_policies", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_expert_external_action_policies_expert_id"), "expert_external_action_policies", ["expert_id"], unique=False)
    op.create_index(op.f("ix_expert_external_action_policies_org_id"), "expert_external_action_policies", ["org_id"], unique=False)
    op.create_index(
        "uq_expert_external_action_policy_tool",
        "expert_external_action_policies",
        ["org_id", "expert_id", "provider", "toolkit_slug", "provider_tool_key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_expert_external_action_policy_tool", table_name="expert_external_action_policies", postgresql_where=sa.text("deleted_at IS NULL"))
    op.drop_index(op.f("ix_expert_external_action_policies_org_id"), table_name="expert_external_action_policies")
    op.drop_index(op.f("ix_expert_external_action_policies_expert_id"), table_name="expert_external_action_policies")
    op.drop_index(op.f("ix_expert_external_action_policies_deleted_at"), table_name="expert_external_action_policies")
    op.drop_table("expert_external_action_policies")
    op.drop_index("uq_integration_accounts_owner_provider_account", table_name="integration_accounts", postgresql_where=sa.text("deleted_at IS NULL"))
    op.drop_index(op.f("ix_integration_accounts_user_id"), table_name="integration_accounts")
    op.drop_index(op.f("ix_integration_accounts_org_id"), table_name="integration_accounts")
    op.drop_index(op.f("ix_integration_accounts_deleted_at"), table_name="integration_accounts")
    op.drop_table("integration_accounts")

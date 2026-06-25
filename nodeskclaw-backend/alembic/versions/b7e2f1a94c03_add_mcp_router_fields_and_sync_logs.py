"""add mcp router fields and sync logs

Revision ID: b7e2f1a94c03
Revises: a468369dcae8
Create Date: 2026-06-25 18:00:00.000000

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b7e2f1a94c03"
down_revision: str | Sequence[str] | None = "a468369dcae8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hermes_mcp_router_sync_logs",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("instance_name", sa.String(length=128), nullable=False),
        sa.Column("profile", sa.String(length=128), nullable=False, server_default="default"),
        sa.Column("mcp_name", sa.String(length=128), nullable=True),
        sa.Column("router_skill_name", sa.String(length=128), nullable=True),
        sa.Column("router_skill_path", sa.Text(), nullable=True),
        sa.Column("tool_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tool_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_hermes_mcp_router_sync_logs_deleted_at"),
        "hermes_mcp_router_sync_logs",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        "ix_hermes_mcp_router_sync_logs_org_agent",
        "hermes_mcp_router_sync_logs",
        ["org_id", "agent_id"],
        unique=False,
    )
    op.create_index(
        "ix_hermes_mcp_router_sync_logs_created_at",
        "hermes_mcp_router_sync_logs",
        ["created_at"],
        unique=False,
    )
    op.add_column(
        "hermes_agent_instances",
        sa.Column("mcp_router_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "hermes_agent_instances",
        sa.Column(
            "mcp_router_skill_name",
            sa.String(length=128),
            nullable=False,
            server_default="nodeskclaw-skill-router",
        ),
    )
    op.add_column(
        "hermes_agent_instances",
        sa.Column("mcp_router_skill_path", sa.Text(), nullable=True),
    )
    op.add_column(
        "hermes_agent_instances",
        sa.Column("mcp_router_tool_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "hermes_agent_instances",
        sa.Column("mcp_router_last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "hermes_agent_instances",
        sa.Column("mcp_router_last_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("hermes_agent_instances", "mcp_router_last_error")
    op.drop_column("hermes_agent_instances", "mcp_router_last_synced_at")
    op.drop_column("hermes_agent_instances", "mcp_router_tool_count")
    op.drop_column("hermes_agent_instances", "mcp_router_skill_path")
    op.drop_column("hermes_agent_instances", "mcp_router_skill_name")
    op.drop_column("hermes_agent_instances", "mcp_router_enabled")
    op.drop_index("ix_hermes_mcp_router_sync_logs_created_at", table_name="hermes_mcp_router_sync_logs")
    op.drop_index("ix_hermes_mcp_router_sync_logs_org_agent", table_name="hermes_mcp_router_sync_logs")
    op.drop_index(op.f("ix_hermes_mcp_router_sync_logs_deleted_at"), table_name="hermes_mcp_router_sync_logs")
    op.drop_table("hermes_mcp_router_sync_logs")

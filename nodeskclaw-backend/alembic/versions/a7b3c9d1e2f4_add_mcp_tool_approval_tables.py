"""add mcp tool approval tables

Revision ID: a7b3c9d1e2f4
Revises: 4f9556c2f8a3
Create Date: 2026-06-14 21:30:00.000000

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a7b3c9d1e2f4"
down_revision: str | Sequence[str] | None = "4f9556c2f8a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_tool_approval_requests",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("requester_user_id", sa.String(length=36), nullable=False),
        sa.Column("desktop_device_id", sa.String(length=200), nullable=True),
        sa.Column("profile_id", sa.String(length=200), nullable=True),
        sa.Column("profile_name", sa.String(length=200), nullable=True),
        sa.Column("instance_id", sa.String(length=36), nullable=True),
        sa.Column("instance_ref", sa.String(length=200), nullable=True),
        sa.Column("tool_name", sa.String(length=200), nullable=False),
        sa.Column("permission", sa.String(length=20), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("request_source", sa.String(length=50), nullable=False),
        sa.Column("request_reason", sa.Text(), nullable=True),
        sa.Column("arguments_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", sa.String(length=36), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_comment", sa.Text(), nullable=True),
        sa.Column("grant_id", sa.String(length=36), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mcp_tool_approval_requests_org_status", "mcp_tool_approval_requests", ["org_id", "status"])
    op.create_index("ix_mcp_tool_approval_requests_requester", "mcp_tool_approval_requests", ["requester_user_id"])
    op.create_index("ix_mcp_tool_approval_requests_tool", "mcp_tool_approval_requests", ["tool_name"])
    op.create_index(op.f("ix_mcp_tool_approval_requests_deleted_at"), "mcp_tool_approval_requests", ["deleted_at"])
    op.create_index(op.f("ix_mcp_tool_approval_requests_org_id"), "mcp_tool_approval_requests", ["org_id"])

    op.create_table(
        "mcp_tool_grants",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("desktop_device_id", sa.String(length=200), nullable=True),
        sa.Column("profile_id", sa.String(length=200), nullable=True),
        sa.Column("profile_name", sa.String(length=200), nullable=True),
        sa.Column("instance_id", sa.String(length=36), nullable=True),
        sa.Column("tool_name", sa.String(length=200), nullable=False),
        sa.Column("permission", sa.String(length=20), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("grant_status", sa.String(length=20), nullable=False),
        sa.Column("approved_by", sa.String(length=36), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_by", sa.String(length=36), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("constraints_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source_request_id", sa.String(length=36), nullable=True),
        sa.Column("policy_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_mcp_tool_grants_active",
        "mcp_tool_grants",
        ["org_id", "user_id", "instance_id", "tool_name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND grant_status = 'active'"),
    )
    op.create_index("ix_mcp_tool_grants_org_status", "mcp_tool_grants", ["org_id", "grant_status"])
    op.create_index("ix_mcp_tool_grants_user", "mcp_tool_grants", ["user_id"])
    op.create_index(op.f("ix_mcp_tool_grants_deleted_at"), "mcp_tool_grants", ["deleted_at"])
    op.create_index(op.f("ix_mcp_tool_grants_org_id"), "mcp_tool_grants", ["org_id"])

    op.create_table(
        "mcp_tool_policy_events",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("target_user_id", sa.String(length=36), nullable=True),
        sa.Column("tool_name", sa.String(length=200), nullable=False),
        sa.Column("instance_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("approval_request_id", sa.String(length=36), nullable=True),
        sa.Column("grant_id", sa.String(length=36), nullable=True),
        sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mcp_tool_policy_events_org_created", "mcp_tool_policy_events", ["org_id", "created_at"])
    op.create_index("ix_mcp_tool_policy_events_tool", "mcp_tool_policy_events", ["tool_name"])
    op.create_index(op.f("ix_mcp_tool_policy_events_deleted_at"), "mcp_tool_policy_events", ["deleted_at"])
    op.create_index(op.f("ix_mcp_tool_policy_events_org_id"), "mcp_tool_policy_events", ["org_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_mcp_tool_policy_events_org_id"), table_name="mcp_tool_policy_events")
    op.drop_index(op.f("ix_mcp_tool_policy_events_deleted_at"), table_name="mcp_tool_policy_events")
    op.drop_index("ix_mcp_tool_policy_events_tool", table_name="mcp_tool_policy_events")
    op.drop_index("ix_mcp_tool_policy_events_org_created", table_name="mcp_tool_policy_events")
    op.drop_table("mcp_tool_policy_events")

    op.drop_index(op.f("ix_mcp_tool_grants_org_id"), table_name="mcp_tool_grants")
    op.drop_index(op.f("ix_mcp_tool_grants_deleted_at"), table_name="mcp_tool_grants")
    op.drop_index("ix_mcp_tool_grants_user", table_name="mcp_tool_grants")
    op.drop_index("ix_mcp_tool_grants_org_status", table_name="mcp_tool_grants")
    op.drop_index("uq_mcp_tool_grants_active", table_name="mcp_tool_grants")
    op.drop_table("mcp_tool_grants")

    op.drop_index(op.f("ix_mcp_tool_approval_requests_org_id"), table_name="mcp_tool_approval_requests")
    op.drop_index(op.f("ix_mcp_tool_approval_requests_deleted_at"), table_name="mcp_tool_approval_requests")
    op.drop_index("ix_mcp_tool_approval_requests_tool", table_name="mcp_tool_approval_requests")
    op.drop_index("ix_mcp_tool_approval_requests_requester", table_name="mcp_tool_approval_requests")
    op.drop_index("ix_mcp_tool_approval_requests_org_status", table_name="mcp_tool_approval_requests")
    op.drop_table("mcp_tool_approval_requests")

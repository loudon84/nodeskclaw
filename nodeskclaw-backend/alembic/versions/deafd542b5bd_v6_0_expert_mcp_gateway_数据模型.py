"""v6.0 expert mcp gateway 数据模型

Revision ID: deafd542b5bd
Revises: d1e97d4d4411
Create Date: 2026-06-27 13:43:36.477975

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "deafd542b5bd"
down_revision: str | Sequence[str] | None = "d1e97d4d4411"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "expert_invocation_logs",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("expert_id", sa.String(length=36), nullable=True),
        sa.Column("expert_skill_id", sa.String(length=36), nullable=True),
        sa.Column("expert_team_id", sa.String(length=36), nullable=True),
        sa.Column("expert_slug", sa.String(length=128), nullable=True),
        sa.Column("skill_name", sa.String(length=128), nullable=True),
        sa.Column("upstream_tool_name", sa.String(length=255), nullable=True),
        sa.Column("agent_alias", sa.String(length=128), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("jsonrpc_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("request_prompt_preview", sa.Text(), nullable=True),
        sa.Column("response_preview", sa.Text(), nullable=True),
        sa.Column("response_content_type", sa.String(length=64), nullable=True),
        sa.Column("response_size_bytes", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("client_source", sa.String(length=64), nullable=True),
        sa.Column("client_version", sa.String(length=64), nullable=True),
        sa.Column("client_device_id", sa.String(length=128), nullable=True),
        sa.Column("parent_invocation_id", sa.String(length=36), nullable=True),
        sa.Column("invocation_type", sa.String(length=32), nullable=False, server_default="expert_skill"),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expert_invocation_logs_deleted_at", "expert_invocation_logs", ["deleted_at"])
    op.create_index("ix_expert_invocation_logs_expert_id", "expert_invocation_logs", ["expert_id"])
    op.create_index("ix_expert_invocation_logs_org_id", "expert_invocation_logs", ["org_id"])
    op.create_index("ix_expert_invocation_logs_parent_invocation_id", "expert_invocation_logs", ["parent_invocation_id"])
    op.create_index("ix_expert_invocation_logs_user_id", "expert_invocation_logs", ["user_id"])
    op.create_index("ix_expert_invocation_org_created", "expert_invocation_logs", ["org_id", "created_at"])
    op.create_index("ix_expert_invocation_org_expert", "expert_invocation_logs", ["org_id", "expert_id"])
    op.create_index("ix_expert_invocation_org_status", "expert_invocation_logs", ["org_id", "status"])

    op.create_table(
        "expert_teams",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("team_slug", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("avatar", sa.String(length=128), nullable=True),
        sa.Column("orchestration_mode", sa.String(length=64), nullable=False, server_default="sequential_gateway"),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expert_teams_deleted_at", "expert_teams", ["deleted_at"])
    op.create_index("ix_expert_teams_org_id", "expert_teams", ["org_id"])
    op.create_index(
        "uq_expert_team_org_slug",
        "expert_teams",
        ["org_id", "team_slug"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "experts",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("hermes_agent_id", sa.String(length=36), nullable=False),
        sa.Column("expert_slug", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("avatar", sa.String(length=128), nullable=True),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["hermes_agent_id"], ["hermes_agent_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expert_org_published", "experts", ["org_id", "published"])
    op.create_index("ix_experts_deleted_at", "experts", ["deleted_at"])
    op.create_index("ix_experts_hermes_agent_id", "experts", ["hermes_agent_id"])
    op.create_index("ix_experts_org_id", "experts", ["org_id"])
    op.create_index(
        "uq_expert_org_slug",
        "experts",
        ["org_id", "expert_slug"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "expert_skills",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("expert_id", sa.String(length=36), nullable=False),
        sa.Column("skill_name", sa.String(length=128), nullable=False),
        sa.Column("upstream_tool_name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("input_schema", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("public", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("call_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("risk_level", sa.String(length=32), nullable=False, server_default="low"),
        sa.Column("approval_mode", sa.String(length=32), nullable=False, server_default="server"),
        sa.Column("output_formats", postgresql.JSONB(astext_type=sa.Text()), server_default='["markdown"]', nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("stale", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["expert_id"], ["experts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expert_skills_deleted_at", "expert_skills", ["deleted_at"])
    op.create_index("ix_expert_skills_expert_id", "expert_skills", ["expert_id"])
    op.create_index("ix_expert_skills_org_id", "expert_skills", ["org_id"])
    op.create_index(
        "uq_expert_skill_org_expert_skill_name",
        "expert_skills",
        ["org_id", "expert_id", "skill_name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_expert_skill_org_expert_upstream",
        "expert_skills",
        ["org_id", "expert_id", "upstream_tool_name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "expert_team_members",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("team_id", sa.String(length=36), nullable=False),
        sa.Column("expert_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=128), nullable=True),
        sa.Column("responsibility", sa.Text(), nullable=True),
        sa.Column("order_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["expert_id"], ["experts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["expert_teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expert_team_member_team_order", "expert_team_members", ["team_id", "order_no"])
    op.create_index("ix_expert_team_members_deleted_at", "expert_team_members", ["deleted_at"])
    op.create_index("ix_expert_team_members_expert_id", "expert_team_members", ["expert_id"])
    op.create_index("ix_expert_team_members_org_id", "expert_team_members", ["org_id"])
    op.create_index("ix_expert_team_members_team_id", "expert_team_members", ["team_id"])

    op.add_column(
        "hermes_agent_instances",
        sa.Column("expert_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("hermes_agent_instances", "expert_enabled")
    op.drop_index("ix_expert_team_members_team_id", table_name="expert_team_members")
    op.drop_index("ix_expert_team_members_org_id", table_name="expert_team_members")
    op.drop_index("ix_expert_team_members_expert_id", table_name="expert_team_members")
    op.drop_index("ix_expert_team_members_deleted_at", table_name="expert_team_members")
    op.drop_index("ix_expert_team_member_team_order", table_name="expert_team_members")
    op.drop_table("expert_team_members")
    op.drop_index("uq_expert_skill_org_expert_upstream", table_name="expert_skills", postgresql_where=sa.text("deleted_at IS NULL"))
    op.drop_index("uq_expert_skill_org_expert_skill_name", table_name="expert_skills", postgresql_where=sa.text("deleted_at IS NULL"))
    op.drop_index("ix_expert_skills_org_id", table_name="expert_skills")
    op.drop_index("ix_expert_skills_expert_id", table_name="expert_skills")
    op.drop_index("ix_expert_skills_deleted_at", table_name="expert_skills")
    op.drop_table("expert_skills")
    op.drop_index("uq_expert_org_slug", table_name="experts", postgresql_where=sa.text("deleted_at IS NULL"))
    op.drop_index("ix_experts_org_id", table_name="experts")
    op.drop_index("ix_experts_hermes_agent_id", table_name="experts")
    op.drop_index("ix_experts_deleted_at", table_name="experts")
    op.drop_index("ix_expert_org_published", table_name="experts")
    op.drop_table("experts")
    op.drop_index("uq_expert_team_org_slug", table_name="expert_teams", postgresql_where=sa.text("deleted_at IS NULL"))
    op.drop_index("ix_expert_teams_org_id", table_name="expert_teams")
    op.drop_index("ix_expert_teams_deleted_at", table_name="expert_teams")
    op.drop_table("expert_teams")
    op.drop_index("ix_expert_invocation_org_status", table_name="expert_invocation_logs")
    op.drop_index("ix_expert_invocation_org_expert", table_name="expert_invocation_logs")
    op.drop_index("ix_expert_invocation_org_created", table_name="expert_invocation_logs")
    op.drop_index("ix_expert_invocation_logs_user_id", table_name="expert_invocation_logs")
    op.drop_index("ix_expert_invocation_logs_parent_invocation_id", table_name="expert_invocation_logs")
    op.drop_index("ix_expert_invocation_logs_org_id", table_name="expert_invocation_logs")
    op.drop_index("ix_expert_invocation_logs_expert_id", table_name="expert_invocation_logs")
    op.drop_index("ix_expert_invocation_logs_deleted_at", table_name="expert_invocation_logs")
    op.drop_table("expert_invocation_logs")

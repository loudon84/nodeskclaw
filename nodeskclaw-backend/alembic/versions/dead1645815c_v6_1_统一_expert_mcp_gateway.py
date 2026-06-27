"""v6.1 统一 Expert MCP Gateway

Revision ID: dead1645815c
Revises: deafd542b5bd
Create Date: 2026-06-27 17:38:09.829441

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "dead1645815c"
down_revision: str | Sequence[str] | None = "deafd542b5bd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "expert_team_skills",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("expert_team_id", sa.String(length=36), nullable=False),
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
        sa.ForeignKeyConstraint(["expert_team_id"], ["expert_teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expert_team_skills_deleted_at", "expert_team_skills", ["deleted_at"])
    op.create_index("ix_expert_team_skills_expert_team_id", "expert_team_skills", ["expert_team_id"])
    op.create_index("ix_expert_team_skills_org_id", "expert_team_skills", ["org_id"])
    op.create_index(
        "uq_expert_team_skill_org_team_skill_name",
        "expert_team_skills",
        ["org_id", "expert_team_id", "skill_name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_expert_team_skill_org_team_upstream",
        "expert_team_skills",
        ["org_id", "expert_team_id", "upstream_tool_name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.add_column("expert_invocation_logs", sa.Column("catalog_kind", sa.String(length=32), nullable=True))
    op.add_column("expert_invocation_logs", sa.Column("catalog_slug", sa.String(length=128), nullable=True))
    op.add_column("expert_invocation_logs", sa.Column("orchestration_mode", sa.String(length=64), nullable=True))

    op.add_column("expert_teams", sa.Column("hermes_agent_id", sa.String(length=36), nullable=True))
    op.create_index("ix_expert_teams_hermes_agent_id", "expert_teams", ["hermes_agent_id"])
    op.create_foreign_key(
        "fk_expert_teams_hermes_agent_id",
        "expert_teams",
        "hermes_agent_instances",
        ["hermes_agent_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute(
        sa.text(
            "UPDATE expert_teams SET orchestration_mode = 'upstream_skill' "
            "WHERE orchestration_mode = 'sequential_gateway'"
        )
    )
    op.alter_column(
        "expert_teams",
        "orchestration_mode",
        server_default="upstream_skill",
        existing_type=sa.String(length=64),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "expert_teams",
        "orchestration_mode",
        server_default="sequential_gateway",
        existing_type=sa.String(length=64),
        existing_nullable=False,
    )
    op.execute(
        sa.text(
            "UPDATE expert_teams SET orchestration_mode = 'sequential_gateway' "
            "WHERE orchestration_mode = 'upstream_skill'"
        )
    )

    op.drop_constraint("fk_expert_teams_hermes_agent_id", "expert_teams", type_="foreignkey")
    op.drop_index("ix_expert_teams_hermes_agent_id", table_name="expert_teams")
    op.drop_column("expert_teams", "hermes_agent_id")

    op.drop_column("expert_invocation_logs", "orchestration_mode")
    op.drop_column("expert_invocation_logs", "catalog_slug")
    op.drop_column("expert_invocation_logs", "catalog_kind")

    op.drop_index("uq_expert_team_skill_org_team_upstream", table_name="expert_team_skills")
    op.drop_index("uq_expert_team_skill_org_team_skill_name", table_name="expert_team_skills")
    op.drop_index("ix_expert_team_skills_org_id", table_name="expert_team_skills")
    op.drop_index("ix_expert_team_skills_expert_team_id", table_name="expert_team_skills")
    op.drop_index("ix_expert_team_skills_deleted_at", table_name="expert_team_skills")
    op.drop_table("expert_team_skills")

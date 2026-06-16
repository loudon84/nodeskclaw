"""hermes v4.2 runtime governance

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-06-15 12:00:00.000000

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d2e3f4a5b6c7"
down_revision: str | Sequence[str] | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hermes_agent_runtime_states",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.String(length=255), nullable=False),
        sa.Column("runtime_status", sa.String(length=32), nullable=False, server_default="enabled"),
        sa.Column("accepting_tasks", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("max_concurrent_tasks", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("current_running_tasks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_health_status", sa.String(length=32), nullable=True),
        sa.Column("last_health_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("maintenance_reason", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_hermes_agent_runtime_org_agent",
        "hermes_agent_runtime_states",
        ["org_id", "agent_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_hermes_agent_runtime_org_status",
        "hermes_agent_runtime_states",
        ["org_id", "runtime_status"],
        unique=False,
    )

    op.create_table(
        "hermes_runtime_controls",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("control_key", sa.String(length=128), nullable=False),
        sa.Column("control_value", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_hermes_runtime_controls_org_key",
        "hermes_runtime_controls",
        ["org_id", "control_key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "hermes_skill_authorization_grants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("skill_id", sa.String(length=255), nullable=False),
        sa.Column("skill_db_id", sa.String(length=36), nullable=True),
        sa.Column("subject_type", sa.String(length=32), nullable=False),
        sa.Column("subject_id", sa.String(length=255), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("can_list", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("can_invoke", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_install", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_manage", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hermes_skill_auth_grant_org_skill",
        "hermes_skill_authorization_grants",
        ["org_id", "skill_id"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_hermes_skill_auth_grant_subject",
        "hermes_skill_authorization_grants",
        ["org_id", "subject_type", "subject_id"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.add_column("hermes_tasks", sa.Column("priority", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("hermes_tasks", sa.Column("queue_group", sa.String(length=64), nullable=True))
    op.add_column("hermes_tasks", sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("hermes_tasks", sa.Column("not_before", sa.DateTime(timezone=True), nullable=True))
    op.add_column("hermes_tasks", sa.Column("max_retry", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("hermes_tasks", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("hermes_tasks", sa.Column("retry_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("hermes_tasks", sa.Column("parent_task_id", sa.String(length=36), nullable=True))
    op.add_column("hermes_tasks", sa.Column("queue_reason", sa.Text(), nullable=True))
    op.add_column("hermes_tasks", sa.Column("queue_entered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("hermes_tasks", sa.Column("run_dispatched_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_hermes_tasks_queue_priority",
        "hermes_tasks",
        ["org_id", "status", "priority", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_hermes_tasks_queue_priority", table_name="hermes_tasks")
    op.drop_column("hermes_tasks", "run_dispatched_at")
    op.drop_column("hermes_tasks", "queue_entered_at")
    op.drop_column("hermes_tasks", "queue_reason")
    op.drop_column("hermes_tasks", "parent_task_id")
    op.drop_column("hermes_tasks", "retry_policy")
    op.drop_column("hermes_tasks", "retry_count")
    op.drop_column("hermes_tasks", "max_retry")
    op.drop_column("hermes_tasks", "not_before")
    op.drop_column("hermes_tasks", "scheduled_at")
    op.drop_column("hermes_tasks", "queue_group")
    op.drop_column("hermes_tasks", "priority")

    op.drop_index("ix_hermes_skill_auth_grant_subject", table_name="hermes_skill_authorization_grants")
    op.drop_index("ix_hermes_skill_auth_grant_org_skill", table_name="hermes_skill_authorization_grants")
    op.drop_table("hermes_skill_authorization_grants")

    op.drop_index("uq_hermes_runtime_controls_org_key", table_name="hermes_runtime_controls")
    op.drop_table("hermes_runtime_controls")

    op.drop_index("ix_hermes_agent_runtime_org_status", table_name="hermes_agent_runtime_states")
    op.drop_index("uq_hermes_agent_runtime_org_agent", table_name="hermes_agent_runtime_states")
    op.drop_table("hermes_agent_runtime_states")

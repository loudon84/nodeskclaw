"""add agent automation tables

Revision ID: 93ebce7657cb
Revises: 7c1f4d8e2a90
Create Date: 2026-10-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "93ebce7657cb"
down_revision: Union[str, Sequence[str], None] = "7c1f4d8e2a90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_automations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("agent_ref", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("prompt_template", sa.Text(), nullable=False),
        sa.Column("input_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("knowledge_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("connector_binding_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("integration_account_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("manual_run_enabled", sa.Boolean(), nullable=False),
        sa.Column("concurrency_policy", sa.String(length=32), nullable=False),
        sa.Column("max_concurrent_runs", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_automations_deleted_at", "agent_automations", ["deleted_at"])
    op.create_index("ix_agent_automations_tenant_id", "agent_automations", ["tenant_id"])
    op.create_index("ix_agent_automations_tenant_status", "agent_automations", ["tenant_id", "status"])
    op.create_index("ix_agent_automations_tenant_owner", "agent_automations", ["tenant_id", "owner_user_id"])

    op.create_table(
        "automation_triggers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("automation_id", sa.String(length=36), nullable=False),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("cron_expr", sa.String(length=128), nullable=True),
        sa.Column("webhook_secret_hash", sa.String(length=128), nullable=True),
        sa.Column("webhook_key_id", sa.String(length=64), nullable=True),
        sa.Column("payload_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("prompt_mapping", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_fire_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_automation_triggers_deleted_at", "automation_triggers", ["deleted_at"])
    op.create_index("ix_automation_triggers_automation_id", "automation_triggers", ["automation_id"])
    op.create_index("ix_automation_triggers_next_fire", "automation_triggers", ["status", "next_fire_at"])
    op.create_index(
        "uq_automation_triggers_automation_type",
        "automation_triggers",
        ["automation_id", "trigger_type"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND trigger_type = 'CRON'"),
    )

    op.create_table(
        "automation_invocations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("automation_id", sa.String(length=36), nullable=False),
        sa.Column("automation_generation", sa.Integer(), nullable=False),
        sa.Column("trigger_id", sa.String(length=36), nullable=True),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
        sa.Column("source_event_id", sa.String(length=256), nullable=True),
        sa.Column("scheduled_fire_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("owner_user_id_snapshot", sa.String(length=36), nullable=False),
        sa.Column("input_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("input_payload_hash", sa.String(length=64), nullable=False),
        sa.Column("rendered_prompt_hash", sa.String(length=64), nullable=False),
        sa.Column("rendered_prompt", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("remote_agent_run_id", sa.String(length=36), nullable=True),
        sa.Column("remote_error_code", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("cancel_requested_by", sa.String(length=36), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_outcome", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_automation_invocations_deleted_at", "automation_invocations", ["deleted_at"])
    op.create_index("ix_automation_invocations_automation_id", "automation_invocations", ["automation_id"])
    op.create_index("ix_automation_invocations_status", "automation_invocations", ["status"])
    op.create_index(
        "uq_automation_invocations_idempotency",
        "automation_invocations",
        ["automation_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_automation_invocations_webhook_event",
        "automation_invocations",
        ["trigger_id", "source_event_id"],
        unique=True,
        postgresql_where=sa.text(
            "deleted_at IS NULL AND trigger_id IS NOT NULL AND source_event_id IS NOT NULL"
        ),
    )
    op.create_index(
        "uq_automation_invocations_cron_fire",
        "automation_invocations",
        ["trigger_id", "scheduled_fire_at"],
        unique=True,
        postgresql_where=sa.text(
            "deleted_at IS NULL AND trigger_id IS NOT NULL AND scheduled_fire_at IS NOT NULL"
        ),
    )

    op.create_table(
        "remote_agent_dispatch_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("invocation_id", sa.String(length=36), nullable=False),
        sa.Column("automation_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("remote_agent_run_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_remote_agent_dispatch_jobs_deleted_at", "remote_agent_dispatch_jobs", ["deleted_at"])
    op.create_index("ix_remote_agent_dispatch_jobs_tenant_id", "remote_agent_dispatch_jobs", ["tenant_id"])
    op.create_index(
        "uq_remote_agent_dispatch_jobs_invocation",
        "remote_agent_dispatch_jobs",
        ["invocation_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_remote_agent_dispatch_jobs_ready",
        "remote_agent_dispatch_jobs",
        ["status", "next_attempt_at"],
    )

    op.create_table(
        "automation_webhook_nonces",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("trigger_id", sa.String(length=36), nullable=False),
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_automation_webhook_nonces_deleted_at", "automation_webhook_nonces", ["deleted_at"])
    op.create_index("ix_automation_webhook_nonces_expires", "automation_webhook_nonces", ["expires_at"])
    op.create_index(
        "uq_automation_webhook_nonces_trigger_nonce",
        "automation_webhook_nonces",
        ["trigger_id", "nonce"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.add_column(
        "task_successor_jobs",
        sa.Column("target_kind", sa.String(length=64), nullable=False, server_default="WORKFLOW_BINDING"),
    )
    op.add_column(
        "task_successor_jobs",
        sa.Column("target_automation_id", sa.String(length=36), nullable=True),
    )
    op.alter_column("task_successor_jobs", "target_workflow_binding_id", existing_type=sa.String(length=36), nullable=True)
    op.drop_index("uq_task_successor_jobs_source_run_target", table_name="task_successor_jobs")
    op.create_index(
        "uq_task_successor_jobs_source_run_binding",
        "task_successor_jobs",
        ["source_run_id", "target_workflow_binding_id"],
        unique=True,
        postgresql_where=sa.text(
            "deleted_at IS NULL AND target_workflow_binding_id IS NOT NULL"
        ),
    )
    op.create_index(
        "uq_task_successor_jobs_source_run_automation",
        "task_successor_jobs",
        ["source_run_id", "target_automation_id"],
        unique=True,
        postgresql_where=sa.text(
            "deleted_at IS NULL AND target_automation_id IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_task_successor_jobs_source_run_automation", table_name="task_successor_jobs")
    op.drop_index("uq_task_successor_jobs_source_run_binding", table_name="task_successor_jobs")
    op.create_index(
        "uq_task_successor_jobs_source_run_target",
        "task_successor_jobs",
        ["source_run_id", "target_workflow_binding_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.alter_column("task_successor_jobs", "target_workflow_binding_id", existing_type=sa.String(length=36), nullable=False)
    op.drop_column("task_successor_jobs", "target_automation_id")
    op.drop_column("task_successor_jobs", "target_kind")
    op.drop_table("automation_webhook_nonces")
    op.drop_table("remote_agent_dispatch_jobs")
    op.drop_table("automation_invocations")
    op.drop_table("automation_triggers")
    op.drop_table("agent_automations")

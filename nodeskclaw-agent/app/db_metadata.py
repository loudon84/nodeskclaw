from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.config import settings

SCHEMA = settings.SKILL_AGENT_SCHEMA

agent_metadata = sa.MetaData(schema=SCHEMA)

runs = sa.Table(
    "runs",
    agent_metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("org_id", sa.String(length=64), nullable=False),
    sa.Column("user_id", sa.String(length=64), nullable=False),
    sa.Column("tool_name", sa.String(length=255), nullable=False),
    sa.Column("skill_id", sa.String(length=64), nullable=True),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("arguments", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column("attempt_id", sa.String(length=36), nullable=True),
    sa.Column("generation", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
    sa.Column("next_event_seq", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("dispatch_id", sa.String(length=64), nullable=True),
    sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    sa.Column("command_digest", sa.String(length=64), nullable=True),
    sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
    sa.Column("worker_id", sa.String(length=64), nullable=True),
    sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    sa.Column("run_session_id", sa.String(length=36), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    schema=SCHEMA,
)

run_attempts = sa.Table(
    "run_attempts",
    agent_metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("run_id", sa.String(length=36), sa.ForeignKey(f'"{SCHEMA}".runs.id'), nullable=False),
    sa.Column("attempt_no", sa.Integer(), nullable=False),
    sa.Column("generation", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
    sa.Column("worker_id", sa.String(length=64), nullable=False),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("error_message", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.UniqueConstraint("run_id", "attempt_no", name="uq_agent_run_attempts_run_attempt"),
    schema=SCHEMA,
)

run_events = sa.Table(
    "run_events",
    agent_metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("run_id", sa.String(length=36), sa.ForeignKey(f'"{SCHEMA}".runs.id'), nullable=False),
    sa.Column("attempt_id", sa.String(length=36), nullable=True),
    sa.Column("event_type", sa.String(length=64), nullable=False),
    sa.Column("event_seq", sa.Integer(), nullable=False),
    sa.Column("source", sa.String(length=64), nullable=False, server_default="agent"),
    sa.Column("source_event_id", sa.String(length=128), nullable=True),
    sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.UniqueConstraint("run_id", "event_seq", name="uq_agent_run_events_run_event_seq"),
    schema=SCHEMA,
)

run_artifacts = sa.Table(
    "run_artifacts",
    agent_metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("run_id", sa.String(length=36), sa.ForeignKey(f'"{SCHEMA}".runs.id'), nullable=False),
    sa.Column("attempt_id", sa.String(length=36), nullable=True),
    sa.Column("step_id", sa.String(length=64), nullable=True),
    sa.Column("name", sa.String(length=255), nullable=False),
    sa.Column("content_type", sa.String(length=128), nullable=False),
    sa.Column("size_bytes", sa.BigInteger(), nullable=False),
    sa.Column("storage_ref", sa.String(length=1024), nullable=False),
    sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
    sa.Column("storage_state", sa.String(length=32), nullable=False, server_default=sa.text("'INIT'")),
    sa.Column("storage_driver", sa.String(length=32), nullable=True, server_default=sa.text("'local'")),
    sa.Column("storage_key", sa.String(length=1024), nullable=True),
    sa.Column("upload_mode", sa.String(length=32), nullable=True, server_default=sa.text("'eager'")),
    sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    sa.Column("state_reason", sa.Text(), nullable=True),
    sa.Column("persisted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    schema=SCHEMA,
)

run_approvals = sa.Table(
    "run_approvals",
    agent_metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("run_id", sa.String(length=36), sa.ForeignKey(f'"{SCHEMA}".runs.id'), nullable=False),
    sa.Column("approval_id", sa.String(length=64), nullable=False),
    sa.Column("decision", sa.String(length=32), nullable=False),
    sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.UniqueConstraint("run_id", "approval_id", name="uq_agent_run_approvals_run_approval"),
    schema=SCHEMA,
)

run_sessions = sa.Table(
    "run_sessions",
    agent_metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("org_id", sa.String(length=64), nullable=False),
    sa.Column("user_id", sa.String(length=64), nullable=False),
    sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    schema=SCHEMA,
)

run_steps = sa.Table(
    "run_steps",
    agent_metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("run_id", sa.String(length=36), sa.ForeignKey(f'"{SCHEMA}".runs.id'), nullable=False),
    sa.Column("step_id", sa.String(length=64), nullable=False),
    sa.Column("owner_role", sa.String(length=32), nullable=False),
    sa.Column("engine", sa.String(length=32), nullable=False),
    sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'PENDING'")),
    sa.Column("depends_on", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
    sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    sa.Column("required_artifacts", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
    sa.Column("attempt_id", sa.String(length=36), nullable=True),
    sa.Column("run_generation", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
    sa.Column("edge_job_id", sa.String(length=64), nullable=True),
    sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column("error_message", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.UniqueConstraint("run_id", "step_id", name="uq_agent_run_steps_run_step"),
    schema=SCHEMA,
)

run_event_rejections = sa.Table(
    "run_event_rejections",
    agent_metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("run_id", sa.String(length=36), sa.ForeignKey(f'"{SCHEMA}".runs.id'), nullable=False),
    sa.Column("event_id", sa.String(length=64), nullable=True),
    sa.Column("source_event_id", sa.String(length=128), nullable=True),
    sa.Column("reason", sa.String(length=64), nullable=False),
    sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    schema=SCHEMA,
)

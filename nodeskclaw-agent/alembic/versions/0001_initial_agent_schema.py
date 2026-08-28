"""Initial schema for Skill Agent execution plane.

Revision ID: 0001_initial_agent_schema
Revises: 
Create Date: 2026-08-28 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial_agent_schema"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = "agent"


def upgrade() -> None:
    op.execute(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')
    
    # If legacy skill_agent schema exists and has runs table while agent does not, migrate tables
    op.execute(f"""
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'skill_agent')
           AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = '{SCHEMA}' AND table_name = 'runs') THEN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'skill_agent' AND table_name = 'runs') THEN
                ALTER TABLE "skill_agent".runs SET SCHEMA "{SCHEMA}";
                ALTER TABLE "skill_agent".run_attempts SET SCHEMA "{SCHEMA}";
                ALTER TABLE "skill_agent".run_events SET SCHEMA "{SCHEMA}";
                ALTER TABLE "skill_agent".run_artifacts SET SCHEMA "{SCHEMA}";
                ALTER TABLE "skill_agent".run_approvals SET SCHEMA "{SCHEMA}";
            END IF;
        END IF;
    END $$;
    """)
    
    op.create_table(
        "runs",
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
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=SCHEMA,
    )
    
    op.create_index(
        "uq_agent_runs_dispatch_id",
        "runs",
        ["org_id", "dispatch_id"],
        unique=True,
        postgresql_where=sa.text("dispatch_id IS NOT NULL"),
        schema=SCHEMA,
    )
    op.create_index(
        "uq_agent_runs_idempotency",
        "runs",
        ["org_id", "user_id", "tool_name", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        schema=SCHEMA,
    )

    op.create_table(
        "run_attempts",
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
        sa.UniqueConstraint("run_id", "attempt_no"),
        schema=SCHEMA,
    )

    op.create_table(
        "run_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey(f'"{SCHEMA}".runs.id'), nullable=False),
        sa.Column("attempt_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_seq", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="agent"),
        sa.Column("source_event_id", sa.String(length=128), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("run_id", "event_seq"),
        schema=SCHEMA,
    )

    op.create_table(
        "run_artifacts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey(f'"{SCHEMA}".runs.id'), nullable=False),
        sa.Column("attempt_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("storage_ref", sa.Text(), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=SCHEMA,
    )

    op.create_table(
        "run_approvals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey(f'"{SCHEMA}".runs.id'), nullable=False),
        sa.Column("approval_id", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("run_id", "approval_id"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("run_approvals", schema=SCHEMA)
    op.drop_table("run_artifacts", schema=SCHEMA)
    op.drop_table("run_events", schema=SCHEMA)
    op.drop_table("run_attempts", schema=SCHEMA)
    op.drop_table("runs", schema=SCHEMA)

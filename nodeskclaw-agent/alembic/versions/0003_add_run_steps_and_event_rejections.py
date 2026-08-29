"""Add run_steps and run_event_rejections tables.

Revision ID: 0003_add_run_steps_and_event_rejections
Revises: 0002_run_sessions
Create Date: 2026-08-28 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0003_add_run_steps_and_event_rejections"
down_revision = "0002_run_sessions"
branch_labels = None
depends_on = None

SCHEMA = "agent"


def upgrade() -> None:
    op.create_table(
        "run_steps",
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

    op.create_index(
        "ix_agent_run_steps_run_id",
        "run_steps",
        ["run_id"],
        unique=False,
        schema=SCHEMA,
    )

    op.create_table(
        "run_event_rejections",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey(f'"{SCHEMA}".runs.id'), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=True),
        sa.Column("source_event_id", sa.String(length=128), nullable=True),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=SCHEMA,
    )

    op.create_index(
        "ix_agent_run_event_rejections_run_id",
        "run_event_rejections",
        ["run_id"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_run_event_rejections_run_id", table_name="run_event_rejections", schema=SCHEMA)
    op.drop_table("run_event_rejections", schema=SCHEMA)
    op.drop_index("ix_agent_run_steps_run_id", table_name="run_steps", schema=SCHEMA)
    op.drop_table("run_steps", schema=SCHEMA)

"""Add run_sessions table and run_session_id foreign key on runs.

Revision ID: 0002_run_sessions
Revises: 0001_initial_agent_schema
Create Date: 2026-08-28 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0002_run_sessions"
down_revision = "0001_initial_agent_schema"
branch_labels = None
depends_on = None

SCHEMA = "agent"


def upgrade() -> None:
    op.create_table(
        "run_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=SCHEMA,
    )

    op.create_index(
        "ix_agent_run_sessions_org_id",
        "run_sessions",
        ["org_id"],
        unique=False,
        schema=SCHEMA,
    )

    op.add_column(
        "runs",
        sa.Column("run_session_id", sa.String(length=36), nullable=True),
        schema=SCHEMA,
    )

    op.create_index(
        "ix_agent_runs_run_session_id",
        "runs",
        ["run_session_id"],
        unique=False,
        postgresql_where=sa.text("run_session_id IS NOT NULL"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_runs_run_session_id", table_name="runs", schema=SCHEMA)
    op.drop_column("runs", "run_session_id", schema=SCHEMA)
    op.drop_index("ix_agent_run_sessions_org_id", table_name="run_sessions", schema=SCHEMA)
    op.drop_table("run_sessions", schema=SCHEMA)

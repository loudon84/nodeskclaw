"""attempt runtime binding

Revision ID: 0007_attempt_runtime_binding
Revises: 0006_run_session_lifecycle
Create Date: 2026-09-04 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_attempt_runtime_binding"
down_revision = "0006_run_session_lifecycle"
branch_labels = None
depends_on = None

SCHEMA = "agent"


def upgrade() -> None:
    op.add_column(
        "run_attempts",
        sa.Column("runtime_type", sa.String(length=32), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "run_attempts",
        sa.Column("runtime_version", sa.String(length=64), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "run_attempts",
        sa.Column("runtime_run_id", sa.String(length=128), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "run_attempts",
        sa.Column("runtime_session_id", sa.String(length=128), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "run_attempts",
        sa.Column("runtime_profile", sa.String(length=128), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "run_attempts",
        sa.Column("runtime_capability_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "run_attempts",
        sa.Column("runtime_idempotency_key", sa.String(length=256), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "run_attempts",
        sa.Column("runtime_bound_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "run_attempts",
        sa.Column("runtime_terminal_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("run_attempts", "runtime_terminal_at", schema=SCHEMA)
    op.drop_column("run_attempts", "runtime_bound_at", schema=SCHEMA)
    op.drop_column("run_attempts", "runtime_idempotency_key", schema=SCHEMA)
    op.drop_column("run_attempts", "runtime_capability_snapshot", schema=SCHEMA)
    op.drop_column("run_attempts", "runtime_profile", schema=SCHEMA)
    op.drop_column("run_attempts", "runtime_session_id", schema=SCHEMA)
    op.drop_column("run_attempts", "runtime_run_id", schema=SCHEMA)
    op.drop_column("run_attempts", "runtime_version", schema=SCHEMA)
    op.drop_column("run_attempts", "runtime_type", schema=SCHEMA)

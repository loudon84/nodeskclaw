"""run session lifecycle columns

Revision ID: 0006_run_session_lifecycle
Revises: 0005_artifact_upload_idempotency_and_step
Create Date: 2026-09-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_run_session_lifecycle"
down_revision = "0005_artifact_upload_idempotency_and_step"
branch_labels = None
depends_on = None

SCHEMA = "agent"


def upgrade() -> None:
    op.add_column(
        "run_sessions",
        sa.Column("context_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        schema=SCHEMA,
    )
    op.add_column(
        "run_sessions",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "run_sessions",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("run_sessions", "expires_at", schema=SCHEMA)
    op.drop_column("run_sessions", "deleted_at", schema=SCHEMA)
    op.drop_column("run_sessions", "context_version", schema=SCHEMA)

"""Add step_id, upload_mode, and idempotency_key columns to run_artifacts.

Revision ID: 0005_artifact_upload_idempotency_and_step
Revises: 0004_artifact_storage_state_and_descriptor
Create Date: 2026-08-29 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0005_artifact_upload_idempotency_and_step"
down_revision = "0004_artifact_storage_state_and_descriptor"
branch_labels = None
depends_on = None

SCHEMA = "agent"


def upgrade() -> None:
    op.add_column(
        "run_artifacts",
        sa.Column("step_id", sa.String(length=64), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "run_artifacts",
        sa.Column("upload_mode", sa.String(length=32), nullable=True, server_default=sa.text("'eager'")),
        schema=SCHEMA,
    )
    op.add_column(
        "run_artifacts",
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_agent_run_artifacts_idempotency",
        "run_artifacts",
        ["run_id", "idempotency_key"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_run_artifacts_idempotency", table_name="run_artifacts", schema=SCHEMA)
    op.drop_column("run_artifacts", "idempotency_key", schema=SCHEMA)
    op.drop_column("run_artifacts", "upload_mode", schema=SCHEMA)
    op.drop_column("run_artifacts", "step_id", schema=SCHEMA)

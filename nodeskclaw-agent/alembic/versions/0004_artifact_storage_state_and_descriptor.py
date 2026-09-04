"""Add storage_state and descriptor columns to run_artifacts.

Revision ID: 0004_artifact_storage_state_and_descriptor
Revises: 0003_add_run_steps_and_event_rejections
Create Date: 2026-08-28 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0004_artifact_storage_state_and_descriptor"
down_revision = "0003_add_run_steps_and_event_rejections"
branch_labels = None
depends_on = None

SCHEMA = "agent"


def upgrade() -> None:
    op.add_column(
        "run_artifacts",
        sa.Column("storage_state", sa.String(length=32), nullable=False, server_default=sa.text("'INIT'")),
        schema=SCHEMA,
    )
    op.add_column(
        "run_artifacts",
        sa.Column("storage_driver", sa.String(length=32), nullable=True, server_default=sa.text("'local'")),
        schema=SCHEMA,
    )
    op.add_column(
        "run_artifacts",
        sa.Column("storage_key", sa.String(length=1024), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "run_artifacts",
        sa.Column("state_reason", sa.Text(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "run_artifacts",
        sa.Column("persisted_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "run_artifacts",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("run_artifacts", "expires_at", schema=SCHEMA)
    op.drop_column("run_artifacts", "persisted_at", schema=SCHEMA)
    op.drop_column("run_artifacts", "state_reason", schema=SCHEMA)
    op.drop_column("run_artifacts", "storage_key", schema=SCHEMA)
    op.drop_column("run_artifacts", "storage_driver", schema=SCHEMA)
    op.drop_column("run_artifacts", "storage_state", schema=SCHEMA)

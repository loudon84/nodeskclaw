"""add_edge_job_fields_and_installation_generations

Revision ID: b7e8f9a0c1d2
Revises: edf20a4b09f0
Create Date: 2026-08-28 16:30:00.000000

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7e8f9a0c1d2"
down_revision: str | Sequence[str] | None = "edf20a4b09f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add new fields to edge_jobs
    op.add_column("edge_jobs", sa.Column("attempt_id", sa.String(length=36), nullable=True))
    op.add_column("edge_jobs", sa.Column("step_id", sa.String(length=128), nullable=True))
    op.add_column("edge_jobs", sa.Column("run_generation", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("edge_jobs", sa.Column("request_trace_id", sa.String(length=128), nullable=True))
    op.add_column("edge_jobs", sa.Column("idempotency_key", sa.String(length=255), nullable=True))
    op.add_column("edge_jobs", sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index(
        "ix_edge_jobs_idempotency",
        "edge_jobs",
        ["org_id", "idempotency_key"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL AND idempotency_key IS NOT NULL"),
    )

    # 2. Add generation fields to hermes_skill_installations
    op.add_column(
        "hermes_skill_installations",
        sa.Column("desired_generation", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "hermes_skill_installations",
        sa.Column("actual_generation", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("hermes_skill_installations", "actual_generation")
    op.drop_column("hermes_skill_installations", "desired_generation")

    op.drop_index(
        "ix_edge_jobs_idempotency",
        table_name="edge_jobs",
        postgresql_where=sa.text("deleted_at IS NULL AND idempotency_key IS NOT NULL"),
    )
    op.drop_column("edge_jobs", "cancel_requested_at")
    op.drop_column("edge_jobs", "idempotency_key")
    op.drop_column("edge_jobs", "request_trace_id")
    op.drop_column("edge_jobs", "run_generation")
    op.drop_column("edge_jobs", "step_id")
    op.drop_column("edge_jobs", "attempt_id")

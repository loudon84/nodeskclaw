"""knowledge v1.2 reconciliation_runs

Revision ID: fd64182b8bad
Revises: a8a72f32a761
Create Date: 2026-08-09 07:46:55.861927

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fd64182b8bad"
down_revision: str | None = "a8a72f32a761"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checked_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("drifted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("repaired_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_reconciliation_runs_started_at", "reconciliation_runs", ["started_at"])
    op.create_index("ix_reconciliation_runs_status", "reconciliation_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_reconciliation_runs_status", table_name="reconciliation_runs")
    op.drop_index("ix_reconciliation_runs_started_at", table_name="reconciliation_runs")
    op.drop_table("reconciliation_runs")

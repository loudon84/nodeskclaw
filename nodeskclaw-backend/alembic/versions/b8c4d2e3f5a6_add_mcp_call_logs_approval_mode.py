"""add mcp_call_logs approval_mode

Revision ID: b8c4d2e3f5a6
Revises: a7b3c9d1e2f4
Create Date: 2026-06-14 22:00:00.000000

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "b8c4d2e3f5a6"
down_revision: str | Sequence[str] | None = "a7b3c9d1e2f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "mcp_call_logs",
        sa.Column("approval_mode", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mcp_call_logs", "approval_mode")

"""rename expert skill public column to is_public

Revision ID: 20f2ae1ed244
Revises: dead1645815c
Create Date: 2026-06-28 01:31:24.786276

"""
from typing import Sequence

from alembic import op


revision: str = "20f2ae1ed244"
down_revision: str | Sequence[str] | None = "dead1645815c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("expert_skills", "public", new_column_name="is_public")
    op.alter_column("expert_team_skills", "public", new_column_name="is_public")


def downgrade() -> None:
    op.alter_column("expert_team_skills", "is_public", new_column_name="public")
    op.alter_column("expert_skills", "is_public", new_column_name="public")

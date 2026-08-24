"""expert_skill_approval_mode_default_auto

Revision ID: 56b72527c1fe
Revises: b1bc120a37db
Create Date: 2026-08-24 19:35:57.118334

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "56b72527c1fe"
down_revision: str | Sequence[str] | None = "b1bc120a37db"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "expert_skills",
        "approval_mode",
        existing_type=sa.String(length=32),
        server_default="auto",
        existing_nullable=False,
    )
    op.alter_column(
        "expert_team_skills",
        "approval_mode",
        existing_type=sa.String(length=32),
        server_default="auto",
        existing_nullable=False,
    )
    op.execute(
        sa.text(
            "UPDATE expert_skills SET approval_mode = 'auto' "
            "WHERE approval_mode = 'server' AND deleted_at IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE expert_team_skills SET approval_mode = 'auto' "
            "WHERE approval_mode = 'server' AND deleted_at IS NULL"
        )
    )


def downgrade() -> None:
    op.alter_column(
        "expert_skills",
        "approval_mode",
        existing_type=sa.String(length=32),
        server_default="server",
        existing_nullable=False,
    )
    op.alter_column(
        "expert_team_skills",
        "approval_mode",
        existing_type=sa.String(length=32),
        server_default="server",
        existing_nullable=False,
    )

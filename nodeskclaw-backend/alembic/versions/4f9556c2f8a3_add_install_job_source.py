"""add install job source

Revision ID: 4f9556c2f8a3
Revises: 179ad652b267
Create Date: 2026-06-14 20:34:22.478203

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f9556c2f8a3'
down_revision: str | Sequence[str] | None = '179ad652b267'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "hermes_skill_install_jobs",
        sa.Column("source", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("hermes_skill_install_jobs", "source")

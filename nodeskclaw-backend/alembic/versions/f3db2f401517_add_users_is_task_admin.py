"""add users is_task_admin

Revision ID: f3db2f401517
Revises: 56b72527c1fe
Create Date: 2026-08-25 09:06:15.111632

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f3db2f401517'
down_revision: str | Sequence[str] | None = '56b72527c1fe'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('is_task_admin', sa.Boolean(), server_default='false', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('users', 'is_task_admin')

"""normalize gene source registry

Revision ID: c355da7aa436
Revises: 6d2f8f1a9b3c
Create Date: 2026-05-28 02:42:01.393212

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c355da7aa436'
down_revision: str | Sequence[str] | None = '6d2f8f1a9b3c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "UPDATE genes SET source_registry = 'local' "
        "WHERE source_registry = 'genehub'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    pass

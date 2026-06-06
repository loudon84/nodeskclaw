"""merge_file_refs_and_hermes_skill

Revision ID: 08837b4eb7b1
Revises: 9b871b5cc694, j0d6e7f8a9b1
Create Date: 2026-06-06 19:08:01.332003

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '08837b4eb7b1'
down_revision: str | Sequence[str] | None = ('9b871b5cc694', 'j0d6e7f8a9b1')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

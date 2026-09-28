"""merge skill run attachment and member tokens heads

Revision ID: 3ed1bd9bd334
Revises: 057e26f2a7e1, d0a8a590ba70
Create Date: 2026-09-26 07:00:53.554558

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ed1bd9bd334'
down_revision: str | Sequence[str] | None = ('057e26f2a7e1', 'd0a8a590ba70')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

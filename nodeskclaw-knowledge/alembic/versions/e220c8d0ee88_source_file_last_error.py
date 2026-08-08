"""source_file_last_error

Revision ID: e220c8d0ee88
Revises: 1acf2f9a5d24
Create Date: 2026-08-08 18:14:43.225216

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e220c8d0ee88"
down_revision: str | None = "1acf2f9a5d24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("source_files", sa.Column("last_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("source_files", "last_error")

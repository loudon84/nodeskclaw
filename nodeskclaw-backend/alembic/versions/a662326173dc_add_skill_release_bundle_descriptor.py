"""add skill release bundle descriptor

Revision ID: a662326173dc
Revises: c2d3e4f5a6b7
Create Date: 2026-08-31 11:45:12.810565

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a662326173dc'
down_revision: str | Sequence[str] | None = 'c2d3e4f5a6b7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("hermes_skill_releases", sa.Column("bundle_ref", sa.String(length=36), nullable=True))
    op.add_column("hermes_skill_releases", sa.Column("bundle_sha256", sa.String(length=64), nullable=True))
    op.add_column("hermes_skill_releases", sa.Column("bundle_size_bytes", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("hermes_skill_releases", "bundle_size_bytes")
    op.drop_column("hermes_skill_releases", "bundle_sha256")
    op.drop_column("hermes_skill_releases", "bundle_ref")

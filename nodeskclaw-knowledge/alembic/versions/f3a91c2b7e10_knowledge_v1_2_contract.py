"""knowledge v1.2 contract origin and retrieval audit fields

Revision ID: f3a91c2b7e10
Revises: e220c8d0ee88
Create Date: 2026-08-08 19:55:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f3a91c2b7e10"
down_revision: str | None = "e220c8d0ee88"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "retrieval_audits",
        sa.Column("origin", sa.String(length=32), nullable=False, server_default="direct_retrieval"),
    )
    op.add_column("retrieval_audits", sa.Column("execution_status", sa.String(length=32), nullable=True))
    op.add_column(
        "retrieval_audits",
        sa.Column("successful_slice_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "retrieval_audits",
        sa.Column("failed_slice_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(op.f("ix_retrieval_audits_origin"), "retrieval_audits", ["origin"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_retrieval_audits_origin"), table_name="retrieval_audits")
    op.drop_column("retrieval_audits", "failed_slice_count")
    op.drop_column("retrieval_audits", "successful_slice_count")
    op.drop_column("retrieval_audits", "execution_status")
    op.drop_column("retrieval_audits", "origin")

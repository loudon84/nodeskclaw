"""knowledge v1.2 metadata schema and source file metadata

Revision ID: a8c4e2f91b30
Revises: f3a91c2b7e10
Create Date: 2026-08-08 21:55:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a8c4e2f91b30"
down_revision: str | None = "f3a91c2b7e10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_bases",
        sa.Column("metadata_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "source_files",
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "source_files",
        sa.Column("metadata_revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "source_files",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("source_files", "archived_at")
    op.drop_column("source_files", "metadata_revision")
    op.drop_column("source_files", "metadata")
    op.drop_column("knowledge_bases", "metadata_schema")

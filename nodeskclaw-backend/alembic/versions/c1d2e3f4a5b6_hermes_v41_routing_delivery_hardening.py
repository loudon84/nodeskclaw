"""hermes v4.1 routing delivery hardening

Revision ID: c1d2e3f4a5b6
Revises: b8c4d2e3f5a6
Create Date: 2026-06-15 10:00:00.000000

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c1d2e3f4a5b6"
down_revision: str | Sequence[str] | None = "b8c4d2e3f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "hermes_skill_installations",
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "hermes_skill_installations",
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "hermes_skill_installations",
        sa.Column("routing_scope", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "hermes_skill_installations",
        sa.Column("routing_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(
        "ix_hermes_skill_installations_routing",
        "hermes_skill_installations",
        ["org_id", "skill_id", "status", "is_default", "priority"],
        unique=False,
    )

    op.add_column("hermes_artifacts", sa.Column("title", sa.String(length=512), nullable=True))
    op.add_column("hermes_artifacts", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("hermes_artifacts", sa.Column("artifact_type", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("hermes_artifacts", "artifact_type")
    op.drop_column("hermes_artifacts", "description")
    op.drop_column("hermes_artifacts", "title")
    op.drop_index("ix_hermes_skill_installations_routing", table_name="hermes_skill_installations")
    op.drop_column("hermes_skill_installations", "routing_metadata")
    op.drop_column("hermes_skill_installations", "routing_scope")
    op.drop_column("hermes_skill_installations", "priority")
    op.drop_column("hermes_skill_installations", "is_default")

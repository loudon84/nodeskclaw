"""v24 build profile artifact types

Revision ID: 14bcac212b54
Revises: b2c8d4e91a06
Create Date: 2026-08-28 11:54:03.780951

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "14bcac212b54"
down_revision: str | None = "b2c8d4e91a06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_build_profiles",
        sa.Column(
            "artifact_types",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "knowledge_build_profiles",
        sa.Column(
            "artifact_trigger_policy",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.alter_column("knowledge_build_profiles", "artifact_types", server_default=None)
    op.alter_column("knowledge_build_profiles", "artifact_trigger_policy", server_default=None)


def downgrade() -> None:
    op.drop_column("knowledge_build_profiles", "artifact_trigger_policy")
    op.drop_column("knowledge_build_profiles", "artifact_types")

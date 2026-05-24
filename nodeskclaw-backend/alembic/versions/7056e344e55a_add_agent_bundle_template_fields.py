"""add_agent_bundle_template_fields

Revision ID: 7056e344e55a
Revises: 4d65cb510bbd
Create Date: 2026-05-22 16:31:17.737850

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7056e344e55a'
down_revision: str | Sequence[str] | None = '4d65cb510bbd'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "instance_templates",
        sa.Column("template_type", sa.String(length=32), nullable=False, server_default="basic"),
    )
    op.add_column("instance_templates", sa.Column("agent_bundle_manifest", sa.Text(), nullable=True))
    op.add_column("instance_templates", sa.Column("bundle_storage_key", sa.String(length=512), nullable=True))
    op.add_column("instance_templates", sa.Column("resource_recommendation", sa.Text(), nullable=True))
    op.add_column("instance_templates", sa.Column("upload_contract", sa.Text(), nullable=True))
    op.add_column("instance_templates", sa.Column("secret_refs", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("instance_templates", "secret_refs")
    op.drop_column("instance_templates", "upload_contract")
    op.drop_column("instance_templates", "resource_recommendation")
    op.drop_column("instance_templates", "bundle_storage_key")
    op.drop_column("instance_templates", "agent_bundle_manifest")
    op.drop_column("instance_templates", "template_type")

"""skill run public attachment metadata

Revision ID: 057e26f2a7e1
Revises: 91713580edeb
Create Date: 2026-09-08 10:45:22.915458

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '057e26f2a7e1'
down_revision: str | Sequence[str] | None = '91713580edeb'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "skill_run_public_attachments",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("attachment_ref", sa.String(length=128), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scan_status", sa.String(length=32), nullable=False),
        sa.Column("scan_reason", sa.String(length=255), nullable=False),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_skill_run_public_attachments_deleted_at"),
        "skill_run_public_attachments",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_skill_run_public_attachments_org_id"),
        "skill_run_public_attachments",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_skill_run_public_attachments_user_id"),
        "skill_run_public_attachments",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_skill_run_public_attachments_org_user_ref",
        "skill_run_public_attachments",
        ["org_id", "user_id", "attachment_ref"],
        unique=False,
    )
    op.create_index(
        "uq_skill_run_public_attachments_ref_alive",
        "skill_run_public_attachments",
        ["attachment_ref"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_skill_run_public_attachments_ref_alive", table_name="skill_run_public_attachments")
    op.drop_index("ix_skill_run_public_attachments_org_user_ref", table_name="skill_run_public_attachments")
    op.drop_index(op.f("ix_skill_run_public_attachments_user_id"), table_name="skill_run_public_attachments")
    op.drop_index(op.f("ix_skill_run_public_attachments_org_id"), table_name="skill_run_public_attachments")
    op.drop_index(op.f("ix_skill_run_public_attachments_deleted_at"), table_name="skill_run_public_attachments")
    op.drop_table("skill_run_public_attachments")


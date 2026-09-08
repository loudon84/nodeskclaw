"""skill run approval decision ledger

Revision ID: 91713580edeb
Revises: f7a8b9c0d1e2
Create Date: 2026-09-07 22:41:42.417613

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "91713580edeb"
down_revision: str | Sequence[str] | None = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "skill_run_approval_decisions",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("approval_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_skill_run_approval_decisions_deleted_at"),
        "skill_run_approval_decisions",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        "uq_skill_run_approval_decisions_alive",
        "skill_run_approval_decisions",
        ["org_id", "user_id", "run_id", "approval_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_skill_run_approval_decisions_alive", table_name="skill_run_approval_decisions")
    op.drop_index(op.f("ix_skill_run_approval_decisions_deleted_at"), table_name="skill_run_approval_decisions")
    op.drop_table("skill_run_approval_decisions")

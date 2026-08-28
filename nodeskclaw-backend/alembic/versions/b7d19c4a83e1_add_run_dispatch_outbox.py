"""add_run_dispatch_outbox

Revision ID: b7d19c4a83e1
Revises: edf20a4b09f0
Create Date: 2026-08-27 10:00:00.000000

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7d19c4a83e1"
down_revision: str | Sequence[str] | None = "edf20a4b09f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("hermes_tasks", sa.Column("projection_cursor", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "run_dispatch_outbox",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("dispatch_id", sa.String(length=64), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("tool_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("command_digest", sa.String(length=64), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatcher_id", sa.String(length=64), nullable=True),
        sa.Column("lease_generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["hermes_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_run_dispatch_outbox_created_at"), "run_dispatch_outbox", ["created_at"], unique=False)
    op.create_index(op.f("ix_run_dispatch_outbox_deleted_at"), "run_dispatch_outbox", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_run_dispatch_outbox_org_id"), "run_dispatch_outbox", ["org_id"], unique=False)
    op.create_index(op.f("ix_run_dispatch_outbox_run_id"), "run_dispatch_outbox", ["run_id"], unique=False)
    op.create_index(op.f("ix_run_dispatch_outbox_status"), "run_dispatch_outbox", ["status"], unique=False)
    op.create_index(
        "uq_run_dispatch_outbox_dispatch_id_alive",
        "run_dispatch_outbox",
        ["org_id", "dispatch_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_run_dispatch_outbox_pending_poll",
        "run_dispatch_outbox",
        ["status", "next_retry_at", "created_at"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL AND (status = 'pending' OR status = 'delivering')"),
    )


def downgrade() -> None:
    op.drop_column("hermes_tasks", "projection_cursor")
    op.drop_index("ix_run_dispatch_outbox_pending_poll", table_name="run_dispatch_outbox")
    op.drop_index("uq_run_dispatch_outbox_dispatch_id_alive", table_name="run_dispatch_outbox")
    op.drop_index(op.f("ix_run_dispatch_outbox_status"), table_name="run_dispatch_outbox")
    op.drop_index(op.f("ix_run_dispatch_outbox_run_id"), table_name="run_dispatch_outbox")
    op.drop_index(op.f("ix_run_dispatch_outbox_org_id"), table_name="run_dispatch_outbox")
    op.drop_index(op.f("ix_run_dispatch_outbox_deleted_at"), table_name="run_dispatch_outbox")
    op.drop_index(op.f("ix_run_dispatch_outbox_created_at"), table_name="run_dispatch_outbox")
    op.drop_table("run_dispatch_outbox")

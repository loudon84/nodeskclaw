"""hermes v4.3 desktop client contract

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-06-16 12:00:00.000000

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e3f4a5b6c7d8"
down_revision: str | Sequence[str] | None = "d2e3f4a5b6c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "hermes_tasks",
        sa.Column("client_context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "hermes_tasks",
        sa.Column("routing_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.create_table(
        "hermes_task_event_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False, server_default="task_events_read"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_hermes_task_event_tokens_org_task",
        "hermes_task_event_tokens",
        ["org_id", "task_id"],
        unique=False,
    )
    op.create_index(
        "ix_hermes_task_event_tokens_expires_at",
        "hermes_task_event_tokens",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_hermes_task_event_tokens_task_id",
        "hermes_task_event_tokens",
        ["task_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_hermes_task_event_tokens_task_id", table_name="hermes_task_event_tokens")
    op.drop_index("ix_hermes_task_event_tokens_expires_at", table_name="hermes_task_event_tokens")
    op.drop_index("ix_hermes_task_event_tokens_org_task", table_name="hermes_task_event_tokens")
    op.drop_table("hermes_task_event_tokens")
    op.drop_column("hermes_tasks", "routing_metadata")
    op.drop_column("hermes_tasks", "client_context")

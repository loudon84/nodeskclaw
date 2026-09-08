"""统一 Skill Run 幂等键

Revision ID: e9802bb694b2
Revises: a662326173dc
Create Date: 2026-08-31 16:52:37.996954

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "e9802bb694b2"
down_revision: str | Sequence[str] | None = "a662326173dc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        "uq_hermes_tasks_idempotency_alive",
        table_name="hermes_tasks",
        postgresql_where=sa.text("deleted_at IS NULL AND idempotency_key IS NOT NULL"),
    )
    op.create_index(
        "uq_hermes_tasks_idempotency_alive",
        "hermes_tasks",
        ["org_id", "user_id", "tool_name", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_hermes_tasks_idempotency_alive",
        table_name="hermes_tasks",
        postgresql_where=sa.text("deleted_at IS NULL AND idempotency_key IS NOT NULL"),
    )
    op.create_index(
        "uq_hermes_tasks_idempotency_alive",
        "hermes_tasks",
        ["org_id", "user_id", "catalog_slug", "tool_name", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND idempotency_key IS NOT NULL"),
    )

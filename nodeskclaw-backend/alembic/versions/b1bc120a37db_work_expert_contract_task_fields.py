"""work expert contract task fields

Revision ID: b1bc120a37db
Revises: b5c9dfed7dde
Create Date: 2026-08-23 10:56:34.801250

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "b1bc120a37db"
down_revision: str | Sequence[str] | None = "b5c9dfed7dde"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("hermes_tasks", sa.Column("result_content", sa.Text(), nullable=True))
    op.add_column("hermes_tasks", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.add_column("hermes_tasks", sa.Column("catalog_slug", sa.String(length=255), nullable=True))
    op.create_index(
        "uq_hermes_tasks_idempotency_alive",
        "hermes_tasks",
        ["org_id", "user_id", "catalog_slug", "tool_name", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_hermes_tasks_idempotency_alive",
        table_name="hermes_tasks",
        postgresql_where=sa.text("deleted_at IS NULL AND idempotency_key IS NOT NULL"),
    )
    op.drop_column("hermes_tasks", "catalog_slug")
    op.drop_column("hermes_tasks", "idempotency_key")
    op.drop_column("hermes_tasks", "result_content")

"""widen source_event_id to 512

Revision ID: f8ff7575827a
Revises: 0007_attempt_runtime_binding
Create Date: 2026-09-06 18:41:59.264787

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "f8ff7575827a"
down_revision: str | Sequence[str] | None = "0007_attempt_runtime_binding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "agent"


def upgrade() -> None:
    op.alter_column(
        "run_events",
        "source_event_id",
        existing_type=sa.VARCHAR(length=128),
        type_=sa.String(length=512),
        existing_nullable=True,
        schema=SCHEMA,
    )
    op.alter_column(
        "run_event_rejections",
        "source_event_id",
        existing_type=sa.VARCHAR(length=128),
        type_=sa.String(length=512),
        existing_nullable=True,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.alter_column(
        "run_event_rejections",
        "source_event_id",
        existing_type=sa.String(length=512),
        type_=sa.VARCHAR(length=128),
        existing_nullable=True,
        schema=SCHEMA,
    )
    op.alter_column(
        "run_events",
        "source_event_id",
        existing_type=sa.String(length=512),
        type_=sa.VARCHAR(length=128),
        existing_nullable=True,
        schema=SCHEMA,
    )

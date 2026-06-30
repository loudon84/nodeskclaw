"""v6.3.1 task request diagnostics

Revision ID: b5c9dfed7dde
Revises: a4b8afdc6ccd
Create Date: 2026-06-30 19:55:00.000000
"""
from typing import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = 'b5c9dfed7dde'
down_revision: str | Sequence[str] | None = 'a4b8afdc6ccd'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('hermes_tasks', sa.Column('request_trace_id', sa.String(64), nullable=True))
    op.add_column('hermes_tasks', sa.Column('request_snapshot', postgresql.JSONB(), nullable=True))
    op.add_column('hermes_tasks', sa.Column('route_diagnostics', postgresql.JSONB(), nullable=True))
    op.create_index('ix_hermes_tasks_request_trace_id', 'hermes_tasks', ['request_trace_id'])
    op.create_index('ix_hermes_tasks_tool_status_created', 'hermes_tasks', ['tool_name', 'status', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_hermes_tasks_tool_status_created', table_name='hermes_tasks')
    op.drop_index('ix_hermes_tasks_request_trace_id', table_name='hermes_tasks')
    op.drop_column('hermes_tasks', 'route_diagnostics')
    op.drop_column('hermes_tasks', 'request_snapshot')
    op.drop_column('hermes_tasks', 'request_trace_id')

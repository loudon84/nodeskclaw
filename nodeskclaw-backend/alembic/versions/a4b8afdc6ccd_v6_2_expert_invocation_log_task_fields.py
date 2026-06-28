"""v6_2_expert_invocation_log_task_fields

Revision ID: a4b8afdc6ccd
Revises: 20f2ae1ed244
Create Date: 2026-06-28 20:31:55.078835

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = 'a4b8afdc6ccd'
down_revision: str | Sequence[str] | None = '20f2ae1ed244'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('expert_invocation_logs', sa.Column('task_id', sa.String(length=36), nullable=True))
    op.add_column('expert_invocation_logs', sa.Column('task_no', sa.String(length=64), nullable=True))
    op.add_column('expert_invocation_logs', sa.Column('event_url', sa.String(length=1024), nullable=True))
    op.add_column('expert_invocation_logs', sa.Column('artifact_url', sa.String(length=1024), nullable=True))
    op.add_column('expert_invocation_logs', sa.Column('hermes_run_id', sa.String(length=255), nullable=True))
    op.add_column('expert_invocation_logs', sa.Column('stream_mode', sa.String(length=32), nullable=True))
    op.create_index('ix_expert_invocation_logs_stream_mode', 'expert_invocation_logs', ['stream_mode'], unique=False)
    op.create_index('ix_expert_invocation_logs_task_id', 'expert_invocation_logs', ['task_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_expert_invocation_logs_task_id', table_name='expert_invocation_logs')
    op.drop_index('ix_expert_invocation_logs_stream_mode', table_name='expert_invocation_logs')
    op.drop_column('expert_invocation_logs', 'stream_mode')
    op.drop_column('expert_invocation_logs', 'hermes_run_id')
    op.drop_column('expert_invocation_logs', 'artifact_url')
    op.drop_column('expert_invocation_logs', 'event_url')
    op.drop_column('expert_invocation_logs', 'task_no')
    op.drop_column('expert_invocation_logs', 'task_id')

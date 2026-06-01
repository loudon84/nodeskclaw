"""add_task_orchestrator_tables

Revision ID: b2c3d4e5f6a7
Revises: c3d8f952a6ea
Create Date: 2026-04-03 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'c3d8f952a6ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # to_workflow_templates
    op.create_table(
        'to_workflow_templates',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('template_key', sa.String(length=128), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('source_type', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='draft'),
        sa.Column('definition_json', postgresql.JSONB(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_to_workflow_templates_template_key', 'to_workflow_templates', ['template_key'])
    op.create_index('ix_to_workflow_templates_deleted_at', 'to_workflow_templates', ['deleted_at'])
    op.execute(
        "CREATE UNIQUE INDEX uq_to_workflow_templates_key_version_alive "
        "ON to_workflow_templates(template_key, version) "
        "WHERE deleted_at IS NULL"
    )

    # to_workflow_instances
    op.create_table(
        'to_workflow_instances',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('template_id', sa.String(length=36), nullable=False),
        sa.Column('template_key', sa.String(length=128), nullable=False),
        sa.Column('thread_id', sa.String(length=128), nullable=False),
        sa.Column('source_type', sa.String(length=64), nullable=False),
        sa.Column('source_ref_id', sa.String(length=128), nullable=False),
        sa.Column('org_id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=True),
        sa.Column('trigger_user_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('input_payload', postgresql.JSONB(), nullable=False),
        sa.Column('runtime_state', postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('current_node_keys', postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('source_trace', postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_checkpoint_id', sa.String(length=128), nullable=True),
        sa.Column('error_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_to_workflow_instances_template_id', 'to_workflow_instances', ['template_id'])
    op.create_index('ix_to_workflow_instances_template_key', 'to_workflow_instances', ['template_key'])
    op.create_index('ix_to_workflow_instances_thread_id', 'to_workflow_instances', ['thread_id'], unique=True)
    op.create_index('ix_to_workflow_instances_source_type', 'to_workflow_instances', ['source_type'])
    op.create_index('ix_to_workflow_instances_source_ref_id', 'to_workflow_instances', ['source_ref_id'])
    op.create_index('ix_to_workflow_instances_org_id', 'to_workflow_instances', ['org_id'])
    op.create_index('ix_to_workflow_instances_workspace_id', 'to_workflow_instances', ['workspace_id'])
    op.create_index('ix_to_workflow_instances_status', 'to_workflow_instances', ['status'])
    op.create_index('ix_to_workflow_instances_deleted_at', 'to_workflow_instances', ['deleted_at'])
    op.execute(
        "CREATE UNIQUE INDEX uq_to_workflow_instances_thread_alive "
        "ON to_workflow_instances(thread_id) "
        "WHERE deleted_at IS NULL"
    )

    # to_workflow_nodes
    op.create_table(
        'to_workflow_nodes',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workflow_instance_id', sa.String(length=36), nullable=False),
        sa.Column('node_key', sa.String(length=128), nullable=False),
        sa.Column('node_type', sa.String(length=64), nullable=False),
        sa.Column('role_code', sa.String(length=64), nullable=True),
        sa.Column('executor_type', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('assigned_agent_id', sa.String(length=36), nullable=True),
        sa.Column('external_run_id', sa.String(length=128), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('timeout_sec', sa.Integer(), nullable=False, server_default='1800'),
        sa.Column('timeout_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('input_payload', postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('output_payload', postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('error_payload', postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('blocked_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_to_workflow_nodes_workflow_instance_id', 'to_workflow_nodes', ['workflow_instance_id'])
    op.create_index('ix_to_workflow_nodes_node_key', 'to_workflow_nodes', ['node_key'])
    op.create_index('ix_to_workflow_nodes_executor_type', 'to_workflow_nodes', ['executor_type'])
    op.create_index('ix_to_workflow_nodes_status', 'to_workflow_nodes', ['status'])
    op.create_index('ix_to_workflow_nodes_assigned_agent_id', 'to_workflow_nodes', ['assigned_agent_id'])
    op.create_index('ix_to_workflow_nodes_external_run_id', 'to_workflow_nodes', ['external_run_id'])
    op.create_index('ix_to_workflow_nodes_deleted_at', 'to_workflow_nodes', ['deleted_at'])
    op.execute(
        "CREATE INDEX idx_to_workflow_nodes_instance_alive "
        "ON to_workflow_nodes(workflow_instance_id) "
        "WHERE deleted_at IS NULL"
    )

    # to_workflow_events
    op.create_table(
        'to_workflow_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workflow_instance_id', sa.String(length=36), nullable=False),
        sa.Column('workflow_node_id', sa.String(length=36), nullable=True),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('event_payload', postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('trace_id', sa.String(length=128), nullable=True),
        sa.Column('created_by_type', sa.String(length=32), nullable=True),
        sa.Column('created_by_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_to_workflow_events_workflow_instance_id', 'to_workflow_events', ['workflow_instance_id'])
    op.create_index('ix_to_workflow_events_workflow_node_id', 'to_workflow_events', ['workflow_node_id'])
    op.create_index('ix_to_workflow_events_event_type', 'to_workflow_events', ['event_type'])
    op.create_index('ix_to_workflow_events_trace_id', 'to_workflow_events', ['trace_id'])
    op.create_index('ix_to_workflow_events_deleted_at', 'to_workflow_events', ['deleted_at'])

    # to_human_interventions
    op.create_table(
        'to_human_interventions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workflow_instance_id', sa.String(length=36), nullable=False),
        sa.Column('workflow_node_id', sa.String(length=36), nullable=True),
        sa.Column('intervention_type', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('requested_by', sa.String(length=36), nullable=True),
        sa.Column('request_payload', postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('response_payload', postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_to_human_interventions_workflow_instance_id', 'to_human_interventions', ['workflow_instance_id'])
    op.create_index('ix_to_human_interventions_workflow_node_id', 'to_human_interventions', ['workflow_node_id'])
    op.create_index('ix_to_human_interventions_intervention_type', 'to_human_interventions', ['intervention_type'])
    op.create_index('ix_to_human_interventions_status', 'to_human_interventions', ['status'])
    op.create_index('ix_to_human_interventions_deleted_at', 'to_human_interventions', ['deleted_at'])

    # to_checkpoints
    op.create_table(
        'to_checkpoints',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workflow_instance_id', sa.String(length=36), nullable=False),
        sa.Column('checkpoint_ns', sa.String(length=128), nullable=False),
        sa.Column('checkpoint_id', sa.String(length=128), nullable=False),
        sa.Column('checkpoint_data', postgresql.JSONB(), nullable=False),
        sa.Column('channel_versions', postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_to_checkpoints_workflow_instance_id', 'to_checkpoints', ['workflow_instance_id'])
    op.create_index('ix_to_checkpoints_checkpoint_ns', 'to_checkpoints', ['checkpoint_ns'])
    op.create_index('ix_to_checkpoints_checkpoint_id', 'to_checkpoints', ['checkpoint_id'])
    op.create_index('ix_to_checkpoints_deleted_at', 'to_checkpoints', ['deleted_at'])

    # to_executor_bindings
    op.create_table(
        'to_executor_bindings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workflow_instance_id', sa.String(length=36), nullable=False),
        sa.Column('workflow_node_id', sa.String(length=36), nullable=False),
        sa.Column('executor_type', sa.String(length=64), nullable=False),
        sa.Column('assigned_agent_id', sa.String(length=36), nullable=True),
        sa.Column('external_run_id', sa.String(length=128), nullable=True),
        sa.Column('callback_mode', sa.String(length=32), nullable=False, server_default='poll'),
        sa.Column('callback_url', sa.String(length=512), nullable=True),
        sa.Column('last_polled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_to_executor_bindings_workflow_instance_id', 'to_executor_bindings', ['workflow_instance_id'])
    op.create_index('ix_to_executor_bindings_workflow_node_id', 'to_executor_bindings', ['workflow_node_id'])
    op.create_index('ix_to_executor_bindings_executor_type', 'to_executor_bindings', ['executor_type'])
    op.create_index('ix_to_executor_bindings_assigned_agent_id', 'to_executor_bindings', ['assigned_agent_id'])
    op.create_index('ix_to_executor_bindings_external_run_id', 'to_executor_bindings', ['external_run_id'])
    op.create_index('ix_to_executor_bindings_deleted_at', 'to_executor_bindings', ['deleted_at'])


def downgrade() -> None:
    op.drop_table('to_executor_bindings')
    op.drop_table('to_checkpoints')
    op.drop_table('to_human_interventions')
    op.drop_table('to_workflow_events')
    op.drop_table('to_workflow_nodes')
    op.drop_table('to_workflow_instances')
    op.drop_table('to_workflow_templates')

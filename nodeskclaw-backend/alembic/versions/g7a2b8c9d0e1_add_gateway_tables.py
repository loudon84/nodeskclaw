"""add gateway tables

Revision ID: g7a2b8c9d0e1
Revises: 30a1bcac4c80, b2c3d4e5f6a7
Create Date: 2026-06-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'g7a2b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = ('30a1bcac4c80', 'b2c3d4e5f6a7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'mcp_gateway_routes',
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('instance_id', sa.String(36), nullable=False),
        sa.Column('mcp_server_ids', postgresql.JSONB(), nullable=False),
        sa.Column('match_tools', postgresql.JSONB(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('org_id', sa.String(36), nullable=False),
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['instance_id'], ['instances.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_mcp_gateway_routes_deleted_at', 'mcp_gateway_routes', ['deleted_at'])
    op.create_index('ix_mcp_gateway_routes_instance_id', 'mcp_gateway_routes', ['instance_id'])
    op.create_index('ix_mcp_gateway_routes_org_id', 'mcp_gateway_routes', ['org_id'])
    op.create_index(
        'ix_mcp_gateway_routes_instance_org', 'mcp_gateway_routes',
        ['instance_id', 'org_id'],
    )
    op.create_index(
        'ix_mcp_gateway_routes_name_org_unique', 'mcp_gateway_routes',
        ['name', 'org_id'], unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )

    op.create_table(
        'mcp_gateway_policies',
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('scope', sa.String(20), nullable=False),
        sa.Column('scope_ref_id', sa.String(36), nullable=True),
        sa.Column('rate_limit_rpm', sa.Integer(), nullable=True),
        sa.Column('max_connections', sa.Integer(), nullable=True),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sensitive_tools', postgresql.JSONB(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('org_id', sa.String(36), nullable=False),
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_mcp_gateway_policies_deleted_at', 'mcp_gateway_policies', ['deleted_at'])
    op.create_index('ix_mcp_gateway_policies_org_id', 'mcp_gateway_policies', ['org_id'])
    op.create_index(
        'ix_mcp_gateway_policies_scope_ref', 'mcp_gateway_policies',
        ['scope', 'scope_ref_id'],
    )
    op.create_index(
        'ix_mcp_gateway_policies_name_org_unique', 'mcp_gateway_policies',
        ['name', 'org_id'], unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )

    op.create_table(
        'mcp_gateway_audit_logs',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('request_id', sa.String(36), nullable=False),
        sa.Column('caller_user_id', sa.String(36), nullable=True),
        sa.Column('caller_org_id', sa.String(36), nullable=True),
        sa.Column('instance_id', sa.String(36), nullable=True),
        sa.Column('mcp_server_id', sa.String(36), nullable=True),
        sa.Column('method', sa.String(50), nullable=False),
        sa.Column('tool_name', sa.String(200), nullable=True),
        sa.Column('request_params_hash', sa.String(64), nullable=True),
        sa.Column('response_status', sa.String(20), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('error_code', sa.Integer(), nullable=True),
        sa.Column('policy_id', sa.String(36), nullable=True),
        sa.Column('is_default_policy', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['instance_id'], ['instances.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_mcp_gateway_audit_logs_request_id', 'mcp_gateway_audit_logs', ['request_id'])
    op.create_index('ix_mcp_gateway_audit_logs_caller_user_id', 'mcp_gateway_audit_logs', ['caller_user_id'])
    op.create_index('ix_mcp_gateway_audit_logs_caller_org_id', 'mcp_gateway_audit_logs', ['caller_org_id'])
    op.create_index('ix_mcp_gateway_audit_logs_instance_id', 'mcp_gateway_audit_logs', ['instance_id'])
    op.create_index('ix_mcp_gateway_audit_logs_mcp_server_id', 'mcp_gateway_audit_logs', ['mcp_server_id'])
    op.create_index('ix_mcp_gateway_audit_logs_tool_name', 'mcp_gateway_audit_logs', ['tool_name'])
    op.create_index(
        'ix_mcp_gateway_audit_logs_instance_created', 'mcp_gateway_audit_logs',
        ['instance_id', 'created_at'],
    )
    op.create_index(
        'ix_mcp_gateway_audit_logs_user_created', 'mcp_gateway_audit_logs',
        ['caller_user_id', 'created_at'],
    )
    op.create_index(
        'ix_mcp_gateway_audit_logs_method_created', 'mcp_gateway_audit_logs',
        ['method', 'created_at'],
    )


def downgrade() -> None:
    op.drop_table('mcp_gateway_audit_logs')
    op.drop_table('mcp_gateway_policies')
    op.drop_table('mcp_gateway_routes')

"""add gateway security tables

Revision ID: h8b3c9d0e1f2
Revises: g7a2b8c9d0e1
Create Date: 2026-06-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'h8b3c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'g7a2b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'mcp_gateway_security_policies',
        sa.Column('org_id', sa.String(36), nullable=False),
        sa.Column('method_whitelist', postgresql.JSONB(), nullable=False),
        sa.Column('max_request_body_bytes', sa.Integer(), nullable=False, server_default='1048576'),
        sa.Column('global_rate_limit_rpm', sa.Integer(), nullable=False, server_default='500'),
        sa.Column('sse_max_connections', sa.Integer(), nullable=False, server_default='500'),
        sa.Column('sse_max_connections_per_instance', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('origin_check_mode', sa.String(10), nullable=False, server_default='relaxed'),
        sa.Column('allowed_origins', postgresql.JSONB(), nullable=False),
        sa.Column('upstream_host_whitelist', postgresql.JSONB(), nullable=False),
        sa.Column('sensitive_param_names', postgresql.JSONB(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_mcp_gateway_sec_policy_org_id', 'mcp_gateway_security_policies', ['org_id'])
    op.create_index('ix_mcp_gateway_sec_policy_deleted_at', 'mcp_gateway_security_policies', ['deleted_at'])
    op.create_index(
        'ix_mcp_gateway_sec_policy_org_unique', 'mcp_gateway_security_policies',
        ['org_id'], unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )

    op.create_table(
        'mcp_gateway_api_keys',
        sa.Column('key_prefix', sa.String(8), nullable=False),
        sa.Column('key_hash', sa.String(64), nullable=False),
        sa.Column('key_suffix', sa.String(4), nullable=False),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('status', sa.String(10), nullable=False, server_default='active'),
        sa.Column('rate_limit_rpm', sa.Integer(), nullable=True),
        sa.Column('allowed_scopes', postgresql.JSONB(), nullable=False),
        sa.Column('last_used_at', sa.String(36), nullable=True),
        sa.Column('org_id', sa.String(36), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_mcp_gateway_api_keys_key_prefix', 'mcp_gateway_api_keys', ['key_prefix'])
    op.create_index('ix_mcp_gateway_api_keys_key_hash', 'mcp_gateway_api_keys', ['key_hash'])
    op.create_index('ix_mcp_gateway_api_keys_status', 'mcp_gateway_api_keys', ['status'])
    op.create_index('ix_mcp_gateway_api_keys_org_id', 'mcp_gateway_api_keys', ['org_id'])
    op.create_index('ix_mcp_gateway_api_keys_deleted_at', 'mcp_gateway_api_keys', ['deleted_at'])
    op.create_index(
        'ix_mcp_gateway_api_keys_prefix_org', 'mcp_gateway_api_keys',
        ['key_prefix', 'org_id'],
    )

    op.add_column('mcp_gateway_audit_logs', sa.Column('caller_ip', sa.String(45), nullable=True))
    op.add_column('mcp_gateway_audit_logs', sa.Column('auth_type', sa.String(10), nullable=True))
    op.add_column('mcp_gateway_audit_logs', sa.Column('auth_key_id', sa.String(36), nullable=True))
    op.add_column('mcp_gateway_audit_logs', sa.Column('params_masked', postgresql.JSONB(), nullable=True))
    op.add_column('mcp_gateway_audit_logs', sa.Column('security_event', sa.String(50), nullable=True))
    op.create_index('ix_mcp_gateway_audit_logs_security_event', 'mcp_gateway_audit_logs', ['security_event'])
    op.create_index('ix_mcp_gateway_audit_logs_auth_type', 'mcp_gateway_audit_logs', ['auth_type'])


def downgrade() -> None:
    op.drop_index('ix_mcp_gateway_audit_logs_auth_type', 'mcp_gateway_audit_logs')
    op.drop_index('ix_mcp_gateway_audit_logs_security_event', 'mcp_gateway_audit_logs')
    op.drop_column('mcp_gateway_audit_logs', 'security_event')
    op.drop_column('mcp_gateway_audit_logs', 'params_masked')
    op.drop_column('mcp_gateway_audit_logs', 'auth_key_id')
    op.drop_column('mcp_gateway_audit_logs', 'auth_type')
    op.drop_column('mcp_gateway_audit_logs', 'caller_ip')
    op.drop_table('mcp_gateway_api_keys')
    op.drop_table('mcp_gateway_security_policies')

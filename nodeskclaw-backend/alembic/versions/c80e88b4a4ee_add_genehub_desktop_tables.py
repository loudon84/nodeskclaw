"""add genehub desktop tables

Revision ID: c80e88b4a4ee
Revises: 9f6394ee1641
Create Date: 2026-06-08 22:58:37.423724

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c80e88b4a4ee'
down_revision: str | Sequence[str] | None = '9f6394ee1641'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('desktop_devices',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('device_name', sa.String(length=128), nullable=False),
    sa.Column('device_fingerprint', sa.String(length=128), nullable=False),
    sa.Column('os_type', sa.String(length=32), nullable=False),
    sa.Column('os_version', sa.String(length=64), nullable=True),
    sa.Column('app_version', sa.String(length=64), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_desktop_devices_deleted_at'), 'desktop_devices', ['deleted_at'], unique=False)
    op.create_index('ix_desktop_devices_org_user', 'desktop_devices', ['org_id', 'user_id'], unique=False, postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_index('uq_desktop_devices_user_fingerprint_active', 'desktop_devices', ['user_id', 'device_fingerprint'], unique=True, postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_table('desktop_hermes_profiles',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('desktop_device_id', sa.String(length=36), nullable=False),
    sa.Column('profile_name', sa.String(length=128), nullable=False),
    sa.Column('hermes_home', sa.Text(), nullable=False),
    sa.Column('runtime_version', sa.String(length=64), nullable=True),
    sa.Column('gateway_url', sa.Text(), nullable=True),
    sa.Column('gateway_port', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('capabilities', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['desktop_device_id'], ['desktop_devices.id'], ),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_desktop_hermes_profiles_deleted_at'), 'desktop_hermes_profiles', ['deleted_at'], unique=False)
    op.create_index('ix_desktop_hermes_profiles_user', 'desktop_hermes_profiles', ['org_id', 'user_id'], unique=False, postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_index('uq_desktop_hermes_profiles_device_profile_active', 'desktop_hermes_profiles', ['desktop_device_id', 'profile_name'], unique=True, postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_table('genehub_entitlements',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('gene_id', sa.String(length=36), nullable=False),
    sa.Column('target_type', sa.String(length=32), nullable=False),
    sa.Column('target_id', sa.String(length=64), nullable=False),
    sa.Column('permission', sa.String(length=32), nullable=False),
    sa.Column('profile_scope', sa.String(length=128), nullable=True),
    sa.Column('created_by', sa.String(length=36), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['gene_id'], ['genes.id'], ),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_genehub_entitlements_deleted_at'), 'genehub_entitlements', ['deleted_at'], unique=False)
    op.create_index('ix_genehub_entitlements_gene', 'genehub_entitlements', ['gene_id'], unique=False, postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_index('ix_genehub_entitlements_target', 'genehub_entitlements', ['org_id', 'target_type', 'target_id'], unique=False, postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_table('hermes_installed_skills',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('desktop_device_id', sa.String(length=36), nullable=False),
    sa.Column('profile_id', sa.String(length=36), nullable=False),
    sa.Column('gene_id', sa.String(length=36), nullable=True),
    sa.Column('gene_slug', sa.String(length=128), nullable=False),
    sa.Column('gene_version', sa.String(length=32), nullable=False),
    sa.Column('skill_name', sa.String(length=128), nullable=False),
    sa.Column('install_path', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('installed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['desktop_device_id'], ['desktop_devices.id'], ),
    sa.ForeignKeyConstraint(['gene_id'], ['genes.id'], ),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['profile_id'], ['desktop_hermes_profiles.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hermes_installed_skills_deleted_at'), 'hermes_installed_skills', ['deleted_at'], unique=False)
    op.create_index('ix_hermes_installed_skills_user', 'hermes_installed_skills', ['org_id', 'user_id'], unique=False, postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_index('uq_hermes_installed_skills_profile_slug_active', 'hermes_installed_skills', ['profile_id', 'gene_slug'], unique=True, postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_table('hermes_skill_install_jobs',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('desktop_device_id', sa.String(length=36), nullable=True),
    sa.Column('profile_id', sa.String(length=36), nullable=True),
    sa.Column('gene_id', sa.String(length=36), nullable=False),
    sa.Column('gene_slug', sa.String(length=128), nullable=False),
    sa.Column('gene_version', sa.String(length=32), nullable=False),
    sa.Column('skill_name', sa.String(length=128), nullable=False),
    sa.Column('job_type', sa.String(length=32), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('install_mode', sa.String(length=32), nullable=False),
    sa.Column('manifest_hash', sa.String(length=128), nullable=True),
    sa.Column('bundle_hash', sa.String(length=128), nullable=True),
    sa.Column('requested_by', sa.String(length=36), nullable=True),
    sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('error_code', sa.String(length=64), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('client_report', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['desktop_device_id'], ['desktop_devices.id'], ),
    sa.ForeignKeyConstraint(['gene_id'], ['genes.id'], ),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['profile_id'], ['desktop_hermes_profiles.id'], ),
    sa.ForeignKeyConstraint(['requested_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_hermes_install_jobs_gene', 'hermes_skill_install_jobs', ['gene_id'], unique=False, postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_index('ix_hermes_install_jobs_profile_status', 'hermes_skill_install_jobs', ['profile_id', 'status'], unique=False, postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_index('ix_hermes_install_jobs_user_status', 'hermes_skill_install_jobs', ['org_id', 'user_id', 'status'], unique=False, postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_index(op.f('ix_hermes_skill_install_jobs_deleted_at'), 'hermes_skill_install_jobs', ['deleted_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_hermes_skill_install_jobs_deleted_at'), table_name='hermes_skill_install_jobs')
    op.drop_index('ix_hermes_install_jobs_user_status', table_name='hermes_skill_install_jobs', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_index('ix_hermes_install_jobs_profile_status', table_name='hermes_skill_install_jobs', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_index('ix_hermes_install_jobs_gene', table_name='hermes_skill_install_jobs', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_table('hermes_skill_install_jobs')
    op.drop_index('uq_hermes_installed_skills_profile_slug_active', table_name='hermes_installed_skills', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_index('ix_hermes_installed_skills_user', table_name='hermes_installed_skills', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_index(op.f('ix_hermes_installed_skills_deleted_at'), table_name='hermes_installed_skills')
    op.drop_table('hermes_installed_skills')
    op.drop_index('ix_genehub_entitlements_target', table_name='genehub_entitlements', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_index('ix_genehub_entitlements_gene', table_name='genehub_entitlements', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_index(op.f('ix_genehub_entitlements_deleted_at'), table_name='genehub_entitlements')
    op.drop_table('genehub_entitlements')
    op.drop_index('uq_desktop_hermes_profiles_device_profile_active', table_name='desktop_hermes_profiles', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_index('ix_desktop_hermes_profiles_user', table_name='desktop_hermes_profiles', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_index(op.f('ix_desktop_hermes_profiles_deleted_at'), table_name='desktop_hermes_profiles')
    op.drop_table('desktop_hermes_profiles')
    op.drop_index('uq_desktop_devices_user_fingerprint_active', table_name='desktop_devices', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_index('ix_desktop_devices_org_user', table_name='desktop_devices', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_index(op.f('ix_desktop_devices_deleted_at'), table_name='desktop_devices')
    op.drop_table('desktop_devices')

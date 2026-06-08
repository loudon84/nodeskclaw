"""add supervisor department employee_no to org_memberships and org_member_skill_grants table

Revision ID: cb90f8a877a4
Revises: 63c9c2f11ed4
Create Date: 2026-06-08 12:57:50.407177

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = 'cb90f8a877a4'
down_revision: str | Sequence[str] | None = '63c9c2f11ed4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'org_member_skill_grants',
        sa.Column('org_id', sa.String(length=36), nullable=False),
        sa.Column('membership_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('skill_db_id', sa.String(length=36), nullable=False),
        sa.Column('skill_id', sa.String(length=255), nullable=False),
        sa.Column('can_list', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('can_invoke', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('can_manage', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('grant_source', sa.String(length=32), nullable=False, server_default='manual'),
        sa.Column('granted_by', sa.String(length=36), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reason', sa.String(length=512), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['granted_by'], ['users.id']),
        sa.ForeignKeyConstraint(['membership_id'], ['org_memberships.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['skill_db_id'], ['hermes_skills.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_org_member_skill_grants_deleted_at'),
        'org_member_skill_grants',
        ['deleted_at'],
        unique=False,
    )
    op.create_index(
        'ix_org_member_skill_grants_membership',
        'org_member_skill_grants',
        ['membership_id'],
        unique=False,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )
    op.create_index(
        'ix_org_member_skill_grants_org_skill',
        'org_member_skill_grants',
        ['org_id', 'skill_id'],
        unique=False,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )
    op.create_index(
        'ix_org_member_skill_grants_org_user',
        'org_member_skill_grants',
        ['org_id', 'user_id'],
        unique=False,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )
    op.create_index(
        'uq_org_member_skill_grant_active',
        'org_member_skill_grants',
        ['membership_id', 'skill_db_id'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )

    op.add_column('org_memberships', sa.Column('department', sa.String(length=128), nullable=True))
    op.add_column('org_memberships', sa.Column('employee_no', sa.String(length=64), nullable=True))
    op.add_column('org_memberships', sa.Column('supervisor_membership_id', sa.String(length=36), nullable=True))
    op.alter_column(
        'org_memberships',
        'job_title',
        existing_type=sa.VARCHAR(length=32),
        type_=sa.String(length=128),
        existing_nullable=True,
    )
    op.create_index(
        'ix_org_memberships_supervisor',
        'org_memberships',
        ['supervisor_membership_id'],
        unique=False,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )
    op.create_foreign_key(
        'fk_org_memberships_supervisor',
        'org_memberships',
        'org_memberships',
        ['supervisor_membership_id'],
        ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_org_memberships_supervisor', 'org_memberships', type_='foreignkey')
    op.drop_index('ix_org_memberships_supervisor', table_name='org_memberships', postgresql_where=sa.text('deleted_at IS NULL'))
    op.alter_column(
        'org_memberships',
        'job_title',
        existing_type=sa.String(length=128),
        type_=sa.VARCHAR(length=32),
        existing_nullable=True,
    )
    op.drop_column('org_memberships', 'supervisor_membership_id')
    op.drop_column('org_memberships', 'employee_no')
    op.drop_column('org_memberships', 'department')

    op.drop_index('uq_org_member_skill_grant_active', table_name='org_member_skill_grants', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_index('ix_org_member_skill_grants_org_user', table_name='org_member_skill_grants', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_index('ix_org_member_skill_grants_org_skill', table_name='org_member_skill_grants', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_index('ix_org_member_skill_grants_membership', table_name='org_member_skill_grants', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_index(op.f('ix_org_member_skill_grants_deleted_at'), table_name='org_member_skill_grants')
    op.drop_table('org_member_skill_grants')

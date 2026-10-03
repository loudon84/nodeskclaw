"""shared integration account ownership grants

Revision ID: f17188f8316b
Revises: bbd652278c1c
Create Date: 2026-10-03 11:20:00.000000

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f17188f8316b"
down_revision: str | Sequence[str] | None = "bbd652278c1c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("integration_accounts", sa.Column("owner_type", sa.String(length=32), nullable=True))
    op.add_column("integration_accounts", sa.Column("owner_id", sa.String(length=36), nullable=True))
    op.add_column("integration_accounts", sa.Column("created_by_user_id", sa.String(length=36), nullable=True))
    op.execute(
        """
        UPDATE integration_accounts
        SET owner_type = 'USER',
            owner_id = user_id,
            created_by_user_id = user_id
        WHERE owner_type IS NULL
        """
    )
    op.alter_column("integration_accounts", "owner_type", existing_type=sa.String(length=32), nullable=False)
    op.alter_column("integration_accounts", "owner_id", existing_type=sa.String(length=36), nullable=False)
    op.drop_index("uq_integration_accounts_owner_provider_account", table_name="integration_accounts")
    op.alter_column("integration_accounts", "user_id", existing_type=sa.String(length=36), nullable=True)
    op.create_index("ix_integration_accounts_owner_id", "integration_accounts", ["owner_id"], unique=False)
    op.create_index(
        "uq_integration_accounts_owner_provider_account",
        "integration_accounts",
        ["org_id", "owner_type", "owner_id", "provider", "connected_account_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_integration_accounts_shared_authorizing",
        "integration_accounts",
        ["org_id", "provider", "toolkit_slug"],
        unique=True,
        postgresql_where=sa.text(
            "deleted_at IS NULL AND owner_type = 'ORGANIZATION' AND status = 'AUTHORIZING'"
        ),
    )

    op.add_column("integration_connect_attempts", sa.Column("initiated_by_user_id", sa.String(length=36), nullable=True))
    op.add_column("integration_connect_attempts", sa.Column("owner_type", sa.String(length=32), nullable=True))
    op.add_column("integration_connect_attempts", sa.Column("owner_id", sa.String(length=36), nullable=True))
    op.add_column("integration_connect_attempts", sa.Column("provider_user_id", sa.String(length=160), nullable=True))
    op.execute(
        """
        UPDATE integration_connect_attempts AS attempt
        SET initiated_by_user_id = attempt.user_id,
            owner_type = COALESCE(account.owner_type, 'USER'),
            owner_id = COALESCE(account.owner_id, attempt.user_id),
            provider_user_id = COALESCE(account.provider_user_id, '')
        FROM integration_accounts AS account
        WHERE attempt.integration_account_id = account.id
        """
    )
    op.execute(
        """
        UPDATE integration_connect_attempts
        SET initiated_by_user_id = COALESCE(initiated_by_user_id, user_id),
            owner_type = COALESCE(owner_type, 'USER'),
            owner_id = COALESCE(owner_id, user_id),
            provider_user_id = COALESCE(provider_user_id, '')
        WHERE initiated_by_user_id IS NULL OR owner_type IS NULL OR owner_id IS NULL
        """
    )
    op.alter_column(
        "integration_connect_attempts",
        "initiated_by_user_id",
        existing_type=sa.String(length=36),
        nullable=False,
    )
    op.alter_column(
        "integration_connect_attempts",
        "owner_type",
        existing_type=sa.String(length=32),
        nullable=False,
    )
    op.alter_column(
        "integration_connect_attempts",
        "owner_id",
        existing_type=sa.String(length=36),
        nullable=False,
    )
    op.alter_column(
        "integration_connect_attempts",
        "provider_user_id",
        existing_type=sa.String(length=160),
        nullable=False,
    )
    op.alter_column("integration_connect_attempts", "user_id", existing_type=sa.String(length=36), nullable=True)

    op.create_table(
        "integration_account_grants",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("integration_account_id", sa.String(length=36), nullable=False),
        sa.Column("subject_type", sa.String(length=32), nullable=False),
        sa.Column("subject_id", sa.String(length=64), nullable=False),
        sa.Column("permission", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["integration_account_id"], ["integration_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_integration_account_grants_deleted_at",
        "integration_account_grants",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        "ix_integration_account_grants_integration_account_id",
        "integration_account_grants",
        ["integration_account_id"],
        unique=False,
    )
    op.create_index("ix_integration_account_grants_org_id", "integration_account_grants", ["org_id"], unique=False)
    op.create_index(
        "uq_integration_account_grants_subject_permission",
        "integration_account_grants",
        ["integration_account_id", "subject_type", "subject_id", "permission"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_integration_account_grants_subject_permission",
        table_name="integration_account_grants",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index("ix_integration_account_grants_org_id", table_name="integration_account_grants")
    op.drop_index(
        "ix_integration_account_grants_integration_account_id",
        table_name="integration_account_grants",
    )
    op.drop_index("ix_integration_account_grants_deleted_at", table_name="integration_account_grants")
    op.drop_table("integration_account_grants")

    op.alter_column("integration_connect_attempts", "user_id", existing_type=sa.String(length=36), nullable=False)
    op.drop_column("integration_connect_attempts", "provider_user_id")
    op.drop_column("integration_connect_attempts", "owner_id")
    op.drop_column("integration_connect_attempts", "owner_type")
    op.drop_column("integration_connect_attempts", "initiated_by_user_id")

    op.drop_index(
        "uq_integration_accounts_shared_authorizing",
        table_name="integration_accounts",
        postgresql_where=sa.text(
            "deleted_at IS NULL AND owner_type = 'ORGANIZATION' AND status = 'AUTHORIZING'"
        ),
    )
    op.drop_index(
        "uq_integration_accounts_owner_provider_account",
        table_name="integration_accounts",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index("ix_integration_accounts_owner_id", table_name="integration_accounts")
    op.execute("UPDATE integration_accounts SET user_id = owner_id WHERE user_id IS NULL")
    op.alter_column("integration_accounts", "user_id", existing_type=sa.String(length=36), nullable=False)
    op.create_index(
        "uq_integration_accounts_owner_provider_account",
        "integration_accounts",
        ["org_id", "user_id", "provider", "connected_account_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_column("integration_accounts", "created_by_user_id")
    op.drop_column("integration_accounts", "owner_id")
    op.drop_column("integration_accounts", "owner_type")

"""knowledge_v2_application_profile_scope

Revision ID: 4beff359ce9a
Revises: b46a6f127c3b
Create Date: 2026-08-26 15:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "4beff359ce9a"
down_revision: str | None = "b46a6f127c3b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_applications",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_member_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("answer_model", sa.String(length=128), nullable=True),
        sa.Column("active_profile_id", sa.String(length=36), nullable=True),
        sa.Column("acl_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("visibility", sa.String(length=32), nullable=False, server_default="private"),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_applications_org_id", "knowledge_applications", ["org_id"])
    op.create_index("ix_knowledge_applications_deleted_at", "knowledge_applications", ["deleted_at"])
    op.create_index(
        "uq_knowledge_application_org_name",
        "knowledge_applications",
        ["org_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "knowledge_application_set_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_set_id", sa.String(length=36), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_knowledge_application_set_items_application_id",
        "knowledge_application_set_items",
        ["application_id"],
    )
    op.create_index(
        "ix_knowledge_application_set_items_knowledge_set_id",
        "knowledge_application_set_items",
        ["knowledge_set_id"],
    )
    op.create_index(
        "ix_knowledge_application_set_items_deleted_at",
        "knowledge_application_set_items",
        ["deleted_at"],
    )
    op.create_index(
        "uq_application_set_item",
        "knowledge_application_set_items",
        ["application_id", "knowledge_set_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "knowledge_application_acl",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("subject_type", sa.String(length=32), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("permission", sa.String(length=32), nullable=False),
        sa.Column("effect", sa.String(length=16), nullable=False, server_default="allow"),
        sa.Column("created_by_member_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_knowledge_application_acl_application_id",
        "knowledge_application_acl",
        ["application_id"],
    )
    op.create_index("ix_knowledge_application_acl_deleted_at", "knowledge_application_acl", ["deleted_at"])
    op.create_index(
        "uq_application_acl",
        "knowledge_application_acl",
        ["application_id", "subject_type", "subject_id", "permission"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.add_column(
        "knowledge_retrieval_profiles",
        sa.Column("application_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "knowledge_retrieval_profiles",
        sa.Column("scope_type", sa.String(length=32), nullable=False, server_default="set"),
    )
    op.alter_column("knowledge_retrieval_profiles", "knowledge_set_id", existing_type=sa.String(length=36), nullable=True)
    op.create_index(
        "ix_knowledge_retrieval_profiles_application_id",
        "knowledge_retrieval_profiles",
        ["application_id"],
    )
    op.execute("UPDATE knowledge_retrieval_profiles SET scope_type = 'set' WHERE scope_type IS NULL OR scope_type = ''")
    op.drop_index("uq_retrieval_profile_set_version", table_name="knowledge_retrieval_profiles")
    op.create_index(
        "uq_retrieval_profile_set_version",
        "knowledge_retrieval_profiles",
        ["knowledge_set_id", "version"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND scope_type = 'set'"),
    )
    op.create_index(
        "uq_retrieval_profile_application_version",
        "knowledge_retrieval_profiles",
        ["application_id", "version"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND scope_type = 'application'"),
    )


def downgrade() -> None:
    op.drop_index("uq_retrieval_profile_application_version", table_name="knowledge_retrieval_profiles")
    op.drop_index("uq_retrieval_profile_set_version", table_name="knowledge_retrieval_profiles")
    op.create_index(
        "uq_retrieval_profile_set_version",
        "knowledge_retrieval_profiles",
        ["knowledge_set_id", "version"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index("ix_knowledge_retrieval_profiles_application_id", table_name="knowledge_retrieval_profiles")
    op.drop_column("knowledge_retrieval_profiles", "scope_type")
    op.drop_column("knowledge_retrieval_profiles", "application_id")
    op.alter_column(
        "knowledge_retrieval_profiles",
        "knowledge_set_id",
        existing_type=sa.String(length=36),
        nullable=False,
    )

    op.drop_index("uq_application_acl", table_name="knowledge_application_acl")
    op.drop_index("ix_knowledge_application_acl_deleted_at", table_name="knowledge_application_acl")
    op.drop_index("ix_knowledge_application_acl_application_id", table_name="knowledge_application_acl")
    op.drop_table("knowledge_application_acl")

    op.drop_index("uq_application_set_item", table_name="knowledge_application_set_items")
    op.drop_index("ix_knowledge_application_set_items_deleted_at", table_name="knowledge_application_set_items")
    op.drop_index("ix_knowledge_application_set_items_knowledge_set_id", table_name="knowledge_application_set_items")
    op.drop_index("ix_knowledge_application_set_items_application_id", table_name="knowledge_application_set_items")
    op.drop_table("knowledge_application_set_items")

    op.drop_index("uq_knowledge_application_org_name", table_name="knowledge_applications")
    op.drop_index("ix_knowledge_applications_deleted_at", table_name="knowledge_applications")
    op.drop_index("ix_knowledge_applications_org_id", table_name="knowledge_applications")
    op.drop_table("knowledge_applications")

"""add_connector_center

Revision ID: a9063125204c
Revises: 63c1ff7c72c3
Create Date: 2026-08-26 16:32:34.462769

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a9063125204c'
down_revision: str | Sequence[str] | None = '63c1ff7c72c3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "edge_nodes",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_edge_nodes_created_at"), "edge_nodes", ["created_at"], unique=False)
    op.create_index(op.f("ix_edge_nodes_deleted_at"), "edge_nodes", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_edge_nodes_org_id"), "edge_nodes", ["org_id"], unique=False)
    op.create_index(
        "uq_edge_nodes_org_name",
        "edge_nodes",
        ["org_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "connector_definitions",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_connector_definitions_created_at"), "connector_definitions", ["created_at"], unique=False)
    op.create_index(op.f("ix_connector_definitions_deleted_at"), "connector_definitions", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_connector_definitions_org_id"), "connector_definitions", ["org_id"], unique=False)
    op.create_index(
        "ix_connector_definitions_org_kind",
        "connector_definitions",
        ["org_id", "kind"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_connector_definitions_org_name",
        "connector_definitions",
        ["org_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "secret_refs",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("edge_node_id", sa.String(length=36), nullable=True),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["edge_node_id"], ["edge_nodes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_secret_refs_created_at"), "secret_refs", ["created_at"], unique=False)
    op.create_index(op.f("ix_secret_refs_deleted_at"), "secret_refs", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_secret_refs_edge_node_id"), "secret_refs", ["edge_node_id"], unique=False)
    op.create_index(op.f("ix_secret_refs_org_id"), "secret_refs", ["org_id"], unique=False)
    op.create_index(
        "uq_secret_refs_org_name",
        "secret_refs",
        ["org_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "connector_instances",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("definition_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("placement", sa.String(length=32), nullable=False),
        sa.Column("edge_node_id", sa.String(length=36), nullable=True),
        sa.Column("secret_ref_id", sa.String(length=36), nullable=True),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["definition_id"], ["connector_definitions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["edge_node_id"], ["edge_nodes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["secret_ref_id"], ["secret_refs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_connector_instances_created_at"), "connector_instances", ["created_at"], unique=False)
    op.create_index(op.f("ix_connector_instances_definition_id"), "connector_instances", ["definition_id"], unique=False)
    op.create_index(op.f("ix_connector_instances_deleted_at"), "connector_instances", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_connector_instances_edge_node_id"), "connector_instances", ["edge_node_id"], unique=False)
    op.create_index(op.f("ix_connector_instances_org_id"), "connector_instances", ["org_id"], unique=False)
    op.create_index(op.f("ix_connector_instances_secret_ref_id"), "connector_instances", ["secret_ref_id"], unique=False)
    op.create_index(
        "ix_connector_instances_org_placement",
        "connector_instances",
        ["org_id", "placement"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_connector_instances_def_name",
        "connector_instances",
        ["definition_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "connector_tools",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("instance_id", sa.String(length=36), nullable=False),
        sa.Column("tool_name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("input_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("extra_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["instance_id"], ["connector_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_connector_tools_created_at"), "connector_tools", ["created_at"], unique=False)
    op.create_index(op.f("ix_connector_tools_deleted_at"), "connector_tools", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_connector_tools_instance_id"), "connector_tools", ["instance_id"], unique=False)
    op.create_index(op.f("ix_connector_tools_org_id"), "connector_tools", ["org_id"], unique=False)
    op.create_index(
        "ix_connector_tools_org_public",
        "connector_tools",
        ["org_id", "is_public"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_connector_tools_instance_name",
        "connector_tools",
        ["instance_id", "tool_name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "skill_connector_bindings",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("skill_release_id", sa.String(length=36), nullable=False),
        sa.Column("connector_instance_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["connector_instance_id"], ["connector_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_release_id"], ["hermes_skill_releases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_skill_connector_bindings_created_at"), "skill_connector_bindings", ["created_at"], unique=False)
    op.create_index(op.f("ix_skill_connector_bindings_connector_instance_id"), "skill_connector_bindings", ["connector_instance_id"], unique=False)
    op.create_index(op.f("ix_skill_connector_bindings_deleted_at"), "skill_connector_bindings", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_skill_connector_bindings_org_id"), "skill_connector_bindings", ["org_id"], unique=False)
    op.create_index(op.f("ix_skill_connector_bindings_skill_release_id"), "skill_connector_bindings", ["skill_release_id"], unique=False)
    op.create_index(
        "uq_skill_connector_bindings_release_instance",
        "skill_connector_bindings",
        ["skill_release_id", "connector_instance_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_skill_connector_bindings_release_instance", table_name="skill_connector_bindings", postgresql_where=sa.text("deleted_at IS NULL"))
    op.drop_index(op.f("ix_skill_connector_bindings_skill_release_id"), table_name="skill_connector_bindings")
    op.drop_index(op.f("ix_skill_connector_bindings_org_id"), table_name="skill_connector_bindings")
    op.drop_index(op.f("ix_skill_connector_bindings_deleted_at"), table_name="skill_connector_bindings")
    op.drop_index(op.f("ix_skill_connector_bindings_connector_instance_id"), table_name="skill_connector_bindings")
    op.drop_index(op.f("ix_skill_connector_bindings_created_at"), table_name="skill_connector_bindings")
    op.drop_table("skill_connector_bindings")

    op.drop_index("uq_connector_tools_instance_name", table_name="connector_tools", postgresql_where=sa.text("deleted_at IS NULL"))
    op.drop_index("ix_connector_tools_org_public", table_name="connector_tools", postgresql_where=sa.text("deleted_at IS NULL"))
    op.drop_index(op.f("ix_connector_tools_org_id"), table_name="connector_tools")
    op.drop_index(op.f("ix_connector_tools_instance_id"), table_name="connector_tools")
    op.drop_index(op.f("ix_connector_tools_deleted_at"), table_name="connector_tools")
    op.drop_index(op.f("ix_connector_tools_created_at"), table_name="connector_tools")
    op.drop_table("connector_tools")

    op.drop_index("uq_connector_instances_def_name", table_name="connector_instances", postgresql_where=sa.text("deleted_at IS NULL"))
    op.drop_index("ix_connector_instances_org_placement", table_name="connector_instances", postgresql_where=sa.text("deleted_at IS NULL"))
    op.drop_index(op.f("ix_connector_instances_secret_ref_id"), table_name="connector_instances")
    op.drop_index(op.f("ix_connector_instances_org_id"), table_name="connector_instances")
    op.drop_index(op.f("ix_connector_instances_edge_node_id"), table_name="connector_instances")
    op.drop_index(op.f("ix_connector_instances_deleted_at"), table_name="connector_instances")
    op.drop_index(op.f("ix_connector_instances_definition_id"), table_name="connector_instances")
    op.drop_index(op.f("ix_connector_instances_created_at"), table_name="connector_instances")
    op.drop_table("connector_instances")

    op.drop_index("uq_secret_refs_org_name", table_name="secret_refs", postgresql_where=sa.text("deleted_at IS NULL"))
    op.drop_index(op.f("ix_secret_refs_org_id"), table_name="secret_refs")
    op.drop_index(op.f("ix_secret_refs_edge_node_id"), table_name="secret_refs")
    op.drop_index(op.f("ix_secret_refs_deleted_at"), table_name="secret_refs")
    op.drop_index(op.f("ix_secret_refs_created_at"), table_name="secret_refs")
    op.drop_table("secret_refs")

    op.drop_index("uq_connector_definitions_org_name", table_name="connector_definitions", postgresql_where=sa.text("deleted_at IS NULL"))
    op.drop_index("ix_connector_definitions_org_kind", table_name="connector_definitions", postgresql_where=sa.text("deleted_at IS NULL"))
    op.drop_index(op.f("ix_connector_definitions_org_id"), table_name="connector_definitions")
    op.drop_index(op.f("ix_connector_definitions_deleted_at"), table_name="connector_definitions")
    op.drop_index(op.f("ix_connector_definitions_created_at"), table_name="connector_definitions")
    op.drop_table("connector_definitions")

    op.drop_index("uq_edge_nodes_org_name", table_name="edge_nodes", postgresql_where=sa.text("deleted_at IS NULL"))
    op.drop_index(op.f("ix_edge_nodes_org_id"), table_name="edge_nodes")
    op.drop_index(op.f("ix_edge_nodes_deleted_at"), table_name="edge_nodes")
    op.drop_index(op.f("ix_edge_nodes_created_at"), table_name="edge_nodes")
    op.drop_table("edge_nodes")

"""hermes v4.4 agent instances gateway runtime

Revision ID: d02510ead853
Revises: e3f4a5b6c7d8
Create Date: 2026-06-16 19:10:03.759871

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d02510ead853"
down_revision: str | Sequence[str] | None = "e3f4a5b6c7d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hermes_agent_instances",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("instance_id", sa.String(length=36), nullable=True),
        sa.Column("profile_name", sa.String(length=128), nullable=False),
        sa.Column("container_name", sa.String(length=255), nullable=False),
        sa.Column("container_id", sa.String(length=128), nullable=True),
        sa.Column("image", sa.String(length=512), nullable=True),
        sa.Column("docker_status", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("docker_health", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("host_ip", sa.String(length=128), nullable=True),
        sa.Column("webui_port", sa.Integer(), nullable=True),
        sa.Column("webui_url", sa.Text(), nullable=True),
        sa.Column("gateway_port", sa.Integer(), nullable=True),
        sa.Column("gateway_url", sa.Text(), nullable=True),
        sa.Column("gateway_status", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("gateway_runtime_status", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("mcp_status", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("instance_dir", sa.Text(), nullable=True),
        sa.Column("data_dir", sa.Text(), nullable=True),
        sa.Column("env_file", sa.Text(), nullable=True),
        sa.Column("compose_file", sa.Text(), nullable=True),
        sa.Column("compose_project", sa.String(length=255), nullable=True),
        sa.Column("managed_mode", sa.String(length=64), nullable=True),
        sa.Column("last_probe_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["instance_id"], ["instances.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hermes_agent_instance_instance_id",
        "hermes_agent_instances",
        ["instance_id"],
        unique=False,
    )
    op.create_index(
        "ix_hermes_agent_instance_org_runtime",
        "hermes_agent_instances",
        ["org_id", "gateway_runtime_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_hermes_agent_instances_deleted_at"),
        "hermes_agent_instances",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        "uq_hermes_agent_instance_org_container",
        "hermes_agent_instances",
        ["org_id", "container_name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_hermes_agent_instance_org_profile",
        "hermes_agent_instances",
        ["org_id", "profile_name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_hermes_agent_instance_org_profile",
        table_name="hermes_agent_instances",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index(
        "uq_hermes_agent_instance_org_container",
        table_name="hermes_agent_instances",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index(op.f("ix_hermes_agent_instances_deleted_at"), table_name="hermes_agent_instances")
    op.drop_index("ix_hermes_agent_instance_org_runtime", table_name="hermes_agent_instances")
    op.drop_index("ix_hermes_agent_instance_instance_id", table_name="hermes_agent_instances")
    op.drop_table("hermes_agent_instances")

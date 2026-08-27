"""add_edge_jobs_and_installation_target

Revision ID: edf20a4b09f0
Revises: a9063125204c
Create Date: 2026-08-26 18:00:25.098752

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "edf20a4b09f0"
down_revision: str | Sequence[str] | None = "a9063125204c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "edge_jobs",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("edge_node_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("tool_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("arguments", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["edge_node_id"], ["edge_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_edge_jobs_created_at"), "edge_jobs", ["created_at"], unique=False)
    op.create_index(op.f("ix_edge_jobs_deleted_at"), "edge_jobs", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_edge_jobs_edge_node_id"), "edge_jobs", ["edge_node_id"], unique=False)
    op.create_index(op.f("ix_edge_jobs_org_id"), "edge_jobs", ["org_id"], unique=False)
    op.create_index(
        "ix_edge_jobs_node_status",
        "edge_jobs",
        ["edge_node_id", "status"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_edge_jobs_run_id",
        "edge_jobs",
        ["run_id"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.add_column(
        "hermes_skill_installations",
        sa.Column("target_kind", sa.String(length=32), nullable=False, server_default="remote"),
    )
    op.add_column("hermes_skill_installations", sa.Column("edge_node_id", sa.String(length=36), nullable=True))
    op.add_column("hermes_skill_installations", sa.Column("actual_status", sa.String(length=64), nullable=True))
    op.add_column(
        "hermes_skill_installations",
        sa.Column("actual_reported_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_hermes_skill_installations_edge_node_id"),
        "hermes_skill_installations",
        ["edge_node_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_hermes_skill_installations_edge_node_id",
        "hermes_skill_installations",
        "edge_nodes",
        ["edge_node_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "uq_hermes_skill_inst_skill_edge",
        "hermes_skill_installations",
        ["skill_id", "edge_node_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND target_kind = 'edge' AND edge_node_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_hermes_skill_inst_skill_edge",
        table_name="hermes_skill_installations",
        postgresql_where=sa.text("deleted_at IS NULL AND target_kind = 'edge' AND edge_node_id IS NOT NULL"),
    )
    op.drop_constraint("fk_hermes_skill_installations_edge_node_id", "hermes_skill_installations", type_="foreignkey")
    op.drop_index(op.f("ix_hermes_skill_installations_edge_node_id"), table_name="hermes_skill_installations")
    op.drop_column("hermes_skill_installations", "actual_reported_at")
    op.drop_column("hermes_skill_installations", "actual_status")
    op.drop_column("hermes_skill_installations", "edge_node_id")
    op.drop_column("hermes_skill_installations", "target_kind")

    op.drop_index("ix_edge_jobs_run_id", table_name="edge_jobs", postgresql_where=sa.text("deleted_at IS NULL"))
    op.drop_index("ix_edge_jobs_node_status", table_name="edge_jobs", postgresql_where=sa.text("deleted_at IS NULL"))
    op.drop_index(op.f("ix_edge_jobs_org_id"), table_name="edge_jobs")
    op.drop_index(op.f("ix_edge_jobs_edge_node_id"), table_name="edge_jobs")
    op.drop_index(op.f("ix_edge_jobs_deleted_at"), table_name="edge_jobs")
    op.drop_index(op.f("ix_edge_jobs_created_at"), table_name="edge_jobs")
    op.drop_table("edge_jobs")

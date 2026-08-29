"""add edge_artifact_on_demand_requests table and merge heads

Revision ID: c2d3e4f5a6b7
Revises: b7d19c4a83e1, b7e8f9a0c1d2
Create Date: 2026-08-29 14:50:00.000000

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c2d3e4f5a6b7"
down_revision: str | Sequence[str] | None = ("b7d19c4a83e1", "b7e8f9a0c1d2")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "edge_artifact_on_demand_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("edge_node_id", sa.String(length=36), sa.ForeignKey("edge_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.String(length=36), sa.ForeignKey("edge_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_id", sa.String(length=36), nullable=True),
        sa.Column("step_id", sa.String(length=128), nullable=True),
        sa.Column("run_generation", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("delivery_generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("artifact_id", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="issued"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_edge_artifact_on_demand_req",
        "edge_artifact_on_demand_requests",
        ["org_id", "job_id", "name", "run_generation"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_edge_artifact_on_demand_node_status",
        "edge_artifact_on_demand_requests",
        ["edge_node_id", "status"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_edge_artifact_on_demand_run_id",
        "edge_artifact_on_demand_requests",
        ["run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_edge_artifact_on_demand_run_id", table_name="edge_artifact_on_demand_requests")
    op.drop_index("ix_edge_artifact_on_demand_node_status", table_name="edge_artifact_on_demand_requests")
    op.drop_index("uq_edge_artifact_on_demand_req", table_name="edge_artifact_on_demand_requests")
    op.drop_table("edge_artifact_on_demand_requests")

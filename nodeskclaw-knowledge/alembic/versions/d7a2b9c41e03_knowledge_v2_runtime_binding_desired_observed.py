"""knowledge_v2_runtime_binding_desired_observed

Revision ID: d7a2b9c41e03
Revises: c3d8e1f92a04
Create Date: 2026-08-27 16:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d7a2b9c41e03"
down_revision: str | None = "f8c2d1a04b19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_runtime_bindings",
        sa.Column("desired_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "knowledge_runtime_bindings",
        sa.Column("observed_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "knowledge_runtime_bindings",
        sa.Column("config_revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "knowledge_runtime_bindings",
        sa.Column("observed_revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "knowledge_runtime_bindings",
        sa.Column("drift_status", sa.String(length=32), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "knowledge_runtime_bindings",
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "knowledge_index_states",
        sa.Column("validation_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "knowledge_index_states",
        sa.Column("coverage_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "knowledge_index_states",
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column("knowledge_runtime_bindings", "config_revision", server_default=None)
    op.alter_column("knowledge_runtime_bindings", "observed_revision", server_default=None)
    op.alter_column("knowledge_runtime_bindings", "drift_status", server_default=None)


def downgrade() -> None:
    op.drop_column("knowledge_index_states", "last_validated_at")
    op.drop_column("knowledge_index_states", "coverage_payload")
    op.drop_column("knowledge_index_states", "validation_payload")
    op.drop_column("knowledge_runtime_bindings", "last_observed_at")
    op.drop_column("knowledge_runtime_bindings", "drift_status")
    op.drop_column("knowledge_runtime_bindings", "observed_revision")
    op.drop_column("knowledge_runtime_bindings", "config_revision")
    op.drop_column("knowledge_runtime_bindings", "observed_config")
    op.drop_column("knowledge_runtime_bindings", "desired_config")

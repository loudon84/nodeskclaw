"""add mcp_call_logs table

Revision ID: dc8e91d57678
Revises: c80e88b4a4ee
Create Date: 2026-06-14 19:28:51.775408

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "dc8e91d57678"
down_revision: str | Sequence[str] | None = "c80e88b4a4ee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_call_logs",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("tool_name", sa.String(length=200), nullable=False),
        sa.Column("instance_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("input_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mcp_call_logs_deleted_at"), "mcp_call_logs", ["deleted_at"], unique=False)
    op.create_index("ix_mcp_call_logs_org_created", "mcp_call_logs", ["org_id", "created_at"], unique=False)
    op.create_index(op.f("ix_mcp_call_logs_org_id"), "mcp_call_logs", ["org_id"], unique=False)
    op.create_index("ix_mcp_call_logs_tool_created", "mcp_call_logs", ["tool_name", "created_at"], unique=False)
    op.create_index(op.f("ix_mcp_call_logs_tool_name"), "mcp_call_logs", ["tool_name"], unique=False)
    op.create_index("ix_mcp_call_logs_user_created", "mcp_call_logs", ["user_id", "created_at"], unique=False)
    op.create_index(op.f("ix_mcp_call_logs_user_id"), "mcp_call_logs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_mcp_call_logs_user_id"), table_name="mcp_call_logs")
    op.drop_index("ix_mcp_call_logs_user_created", table_name="mcp_call_logs")
    op.drop_index(op.f("ix_mcp_call_logs_tool_name"), table_name="mcp_call_logs")
    op.drop_index("ix_mcp_call_logs_tool_created", table_name="mcp_call_logs")
    op.drop_index(op.f("ix_mcp_call_logs_org_id"), table_name="mcp_call_logs")
    op.drop_index("ix_mcp_call_logs_org_created", table_name="mcp_call_logs")
    op.drop_index(op.f("ix_mcp_call_logs_deleted_at"), table_name="mcp_call_logs")
    op.drop_table("mcp_call_logs")

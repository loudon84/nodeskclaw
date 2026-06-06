"""add_hermes_task_event_artifact_audit_and_installation_fields

Revision ID: j0d6e7f8a9b1
Revises: i9c4d5e6f7a8
Create Date: 2026-06-06 12:00:00.000000

NOTE: This migration was handwritten because the database was not available
for autogenerate. When a database connection is available, please verify by
running: alembic revision --autogenerate -m "verify_audit_and_health_url_fields"
and compare the output.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "j0d6e7f8a9b1"
down_revision: str | Sequence[str] | None = "i9c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "mcp_gateway_audit_logs",
        sa.Column("request_summary", sa.String(500), nullable=True),
    )
    op.add_column(
        "mcp_gateway_audit_logs",
        sa.Column("request_params_redacted", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "mcp_gateway_audit_logs",
        sa.Column("artifact_ids", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "mcp_gateway_audit_logs",
        sa.Column("upstream_request_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "mcp_gateway_audit_logs",
        sa.Column("client_ip", sa.String(45), nullable=True),
    )
    op.add_column(
        "mcp_gateway_audit_logs",
        sa.Column("user_agent", sa.String(500), nullable=True),
    )
    op.add_column(
        "mcp_gateway_audit_logs",
        sa.Column("source_client", sa.String(100), nullable=True),
    )
    op.add_column(
        "mcp_gateway_audit_logs",
        sa.Column("retry_count_used", sa.Integer(), nullable=True),
    )
    op.add_column(
        "mcp_gateway_audit_logs",
        sa.Column("final_upstream_server_id", sa.String(36), nullable=True),
    )
    op.add_column(
        "mcp_gateway_audit_logs",
        sa.Column("final_error_reason", sa.String(500), nullable=True),
    )
    op.add_column(
        "instance_mcp_servers",
        sa.Column("health_url", sa.String(1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mcp_gateway_audit_logs", "final_error_reason")
    op.drop_column("mcp_gateway_audit_logs", "final_upstream_server_id")
    op.drop_column("mcp_gateway_audit_logs", "retry_count_used")
    op.drop_column("mcp_gateway_audit_logs", "source_client")
    op.drop_column("mcp_gateway_audit_logs", "user_agent")
    op.drop_column("mcp_gateway_audit_logs", "client_ip")
    op.drop_column("mcp_gateway_audit_logs", "upstream_request_id")
    op.drop_column("mcp_gateway_audit_logs", "artifact_ids")
    op.drop_column("mcp_gateway_audit_logs", "request_params_redacted")
    op.drop_column("mcp_gateway_audit_logs", "request_summary")
    op.drop_column("instance_mcp_servers", "health_url")

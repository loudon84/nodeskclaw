"""extend mcp_call_logs v661

Revision ID: 179ad652b267
Revises: dc8e91d57678
Create Date: 2026-06-14 20:05:09.484087

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '179ad652b267'
down_revision: str | Sequence[str] | None = 'dc8e91d57678'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("mcp_call_logs", sa.Column("client_name", sa.String(length=200), nullable=True))
    op.add_column("mcp_call_logs", sa.Column("permission", sa.String(length=20), nullable=True))
    op.add_column("mcp_call_logs", sa.Column("risk_level", sa.String(length=20), nullable=True))
    op.add_column(
        "mcp_call_logs",
        sa.Column("result_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mcp_call_logs", "result_summary")
    op.drop_column("mcp_call_logs", "risk_level")
    op.drop_column("mcp_call_logs", "permission")
    op.drop_column("mcp_call_logs", "client_name")

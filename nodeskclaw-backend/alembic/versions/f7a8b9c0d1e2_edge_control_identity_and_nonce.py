"""edge control identity and nonce

Revision ID: f7a8b9c0d1e2
Revises: e9802bb694b2
Create Date: 2026-09-02 18:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "e9802bb694b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("edge_nodes", sa.Column("bootstrap_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("edge_nodes", sa.Column("bootstrap_consumed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "edge_nodes",
        sa.Column("identity_version", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("edge_nodes", sa.Column("public_key", sa.String(length=512), nullable=True))
    op.add_column("edge_nodes", sa.Column("previous_public_key", sa.String(length=512), nullable=True))
    op.add_column("edge_nodes", sa.Column("identity_rotation_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("edge_nodes", sa.Column("identity_revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "edge_nodes",
        sa.Column("last_request_seq", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_table(
        "edge_control_nonces",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("node_id", sa.String(length=36), nullable=False),
        sa.Column("identity_version", sa.Integer(), nullable=False),
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["node_id"], ["edge_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_edge_control_nonces_node_id"), "edge_control_nonces", ["node_id"], unique=False)
    op.create_index(
        "uq_edge_control_nonces_node_identity_nonce",
        "edge_control_nonces",
        ["node_id", "identity_version", "nonce"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_edge_control_nonces_node_identity_nonce", table_name="edge_control_nonces")
    op.drop_index(op.f("ix_edge_control_nonces_node_id"), table_name="edge_control_nonces")
    op.drop_table("edge_control_nonces")
    op.drop_column("edge_nodes", "last_request_seq")
    op.drop_column("edge_nodes", "identity_revoked_at")
    op.drop_column("edge_nodes", "identity_rotation_expires_at")
    op.drop_column("edge_nodes", "previous_public_key")
    op.drop_column("edge_nodes", "public_key")
    op.drop_column("edge_nodes", "identity_version")
    op.drop_column("edge_nodes", "bootstrap_consumed_at")
    op.drop_column("edge_nodes", "bootstrap_expires_at")

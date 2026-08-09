"""knowledge v1.3 source provenance schema

Revision ID: d1e4f7a92b05
Revises: c9f2a8b14e31
Create Date: 2026-08-09 16:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d1e4f7a92b05"
down_revision: str | None = "c9f2a8b14e31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "source_files",
        sa.Column("source_kind", sa.String(length=32), nullable=False, server_default="manual"),
    )
    op.add_column("source_files", sa.Column("connector_id", sa.String(length=36), nullable=True))
    op.add_column("source_files", sa.Column("external_object_id", sa.String(length=512), nullable=True))
    op.add_column("source_files", sa.Column("source_uri", sa.Text(), nullable=True))
    op.add_column("source_files", sa.Column("source_path", sa.Text(), nullable=True))
    op.add_column("source_files", sa.Column("source_revision", sa.String(length=256), nullable=True))
    op.add_column("source_files", sa.Column("source_etag", sa.String(length=256), nullable=True))
    op.add_column(
        "source_files",
        sa.Column("source_modified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "source_files",
        sa.Column(
            "source_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column("source_files", sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("source_files", sa.Column("sync_state", sa.String(length=32), nullable=True))
    op.add_column("source_files", sa.Column("archive_reason", sa.String(length=64), nullable=True))
    op.create_index("ix_source_files_connector_id", "source_files", ["connector_id"])

    op.drop_index("uq_source_file_kb_name", table_name="source_files")
    op.create_index(
        "uq_source_file_kb_name_manual",
        "source_files",
        ["knowledge_base_id", "file_name"],
        unique=True,
        postgresql_where=sa.text("connector_id IS NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "uq_source_file_connector_object",
        "source_files",
        ["connector_id", "external_object_id"],
        unique=True,
        postgresql_where=sa.text("connector_id IS NOT NULL AND deleted_at IS NULL"),
    )

    op.add_column(
        "source_file_versions",
        sa.Column("origin_connector_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "source_file_versions",
        sa.Column("origin_external_revision", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "source_file_versions",
        sa.Column("origin_etag", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "source_file_versions",
        sa.Column("source_snapshot_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "source_file_versions",
        sa.Column("created_by_actor_type", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "source_file_versions",
        sa.Column("created_by_actor_id", sa.String(length=64), nullable=True),
    )
    op.alter_column(
        "source_file_versions",
        "uploaded_by_member_id",
        existing_type=sa.String(length=36),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "source_file_versions",
        "uploaded_by_member_id",
        existing_type=sa.String(length=36),
        nullable=False,
    )
    op.drop_column("source_file_versions", "created_by_actor_id")
    op.drop_column("source_file_versions", "created_by_actor_type")
    op.drop_column("source_file_versions", "source_snapshot_at")
    op.drop_column("source_file_versions", "origin_etag")
    op.drop_column("source_file_versions", "origin_external_revision")
    op.drop_column("source_file_versions", "origin_connector_id")

    op.drop_index("uq_source_file_connector_object", table_name="source_files")
    op.drop_index("uq_source_file_kb_name_manual", table_name="source_files")
    op.create_index(
        "uq_source_file_kb_name",
        "source_files",
        ["knowledge_base_id", "file_name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.drop_index("ix_source_files_connector_id", table_name="source_files")
    op.drop_column("source_files", "archive_reason")
    op.drop_column("source_files", "sync_state")
    op.drop_column("source_files", "last_synced_at")
    op.drop_column("source_files", "source_metadata")
    op.drop_column("source_files", "source_modified_at")
    op.drop_column("source_files", "source_etag")
    op.drop_column("source_files", "source_revision")
    op.drop_column("source_files", "source_path")
    op.drop_column("source_files", "source_uri")
    op.drop_column("source_files", "external_object_id")
    op.drop_column("source_files", "connector_id")
    op.drop_column("source_files", "source_kind")

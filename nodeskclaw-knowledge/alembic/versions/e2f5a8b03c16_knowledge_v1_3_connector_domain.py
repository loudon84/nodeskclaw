"""knowledge v1.3 connector domain tables

Revision ID: e2f5a8b03c16
Revises: d1e4f7a92b05
Create Date: 2026-08-09 16:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e2f5a8b03c16"
down_revision: str | None = "d1e4f7a92b05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_source_connectors",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("connector_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="provisioning"),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("credential_id", sa.String(length=36), nullable=True),
        sa.Column("owner_member_id", sa.String(length=36), nullable=False),
        sa.Column("sync_mode", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("sync_interval_seconds", sa.Integer(), nullable=True),
        sa.Column("sync_cursor", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_sync_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_succeeded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_source_connectors_org_id", "knowledge_source_connectors", ["org_id"])
    op.create_index(
        "ix_knowledge_source_connectors_knowledge_base_id",
        "knowledge_source_connectors",
        ["knowledge_base_id"],
    )
    op.create_index(
        "ix_knowledge_source_connectors_deleted_at",
        "knowledge_source_connectors",
        ["deleted_at"],
    )
    op.create_index(
        "uq_connector_org_kb_name",
        "knowledge_source_connectors",
        ["org_id", "knowledge_base_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "knowledge_connector_credentials",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("connector_id", sa.String(length=36), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_by_member_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_knowledge_connector_credentials_connector_id",
        "knowledge_connector_credentials",
        ["connector_id"],
    )
    op.create_index(
        "ix_knowledge_connector_credentials_deleted_at",
        "knowledge_connector_credentials",
        ["deleted_at"],
    )
    op.create_index(
        "uq_connector_credential_connector_id",
        "knowledge_connector_credentials",
        ["connector_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "knowledge_connector_source_objects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("connector_id", sa.String(length=36), nullable=False),
        sa.Column("external_object_id", sa.String(length=512), nullable=False),
        sa.Column("source_file_id", sa.String(length=36), nullable=True),
        sa.Column("canonical_uri", sa.Text(), nullable=True),
        sa.Column("display_path", sa.Text(), nullable=True),
        sa.Column("external_revision", sa.String(length=256), nullable=True),
        sa.Column("etag", sa.String(length=256), nullable=True),
        sa.Column("source_modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "source_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("last_seen_sync_run_id", sa.String(length=36), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_content_sha256", sa.String(length=64), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_knowledge_connector_source_objects_connector_id",
        "knowledge_connector_source_objects",
        ["connector_id"],
    )
    op.create_index(
        "ix_knowledge_connector_source_objects_source_file_id",
        "knowledge_connector_source_objects",
        ["source_file_id"],
    )
    op.create_index(
        "ix_knowledge_connector_source_objects_deleted_at",
        "knowledge_connector_source_objects",
        ["deleted_at"],
    )
    op.create_index(
        "uq_connector_source_object_ext",
        "knowledge_connector_source_objects",
        ["connector_id", "external_object_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "knowledge_connector_sync_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("connector_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_token", sa.String(length=64), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trigger", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("cursor_before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("cursor_after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_member_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_knowledge_connector_sync_runs_connector_id",
        "knowledge_connector_sync_runs",
        ["connector_id"],
    )
    op.create_index(
        "ix_knowledge_connector_sync_runs_status",
        "knowledge_connector_sync_runs",
        ["status"],
    )
    op.create_index(
        "ix_knowledge_connector_sync_runs_deleted_at",
        "knowledge_connector_sync_runs",
        ["deleted_at"],
    )

    op.create_table(
        "knowledge_connector_sync_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("sync_run_id", sa.String(length=36), nullable=False),
        sa.Column("source_object_id", sa.String(length=36), nullable=True),
        sa.Column("source_file_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("ingestion_job_id", sa.String(length=36), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_knowledge_connector_sync_items_sync_run_id",
        "knowledge_connector_sync_items",
        ["sync_run_id"],
    )
    op.create_index(
        "ix_knowledge_connector_sync_items_source_object_id",
        "knowledge_connector_sync_items",
        ["source_object_id"],
    )
    op.create_index(
        "ix_knowledge_connector_sync_items_source_file_id",
        "knowledge_connector_sync_items",
        ["source_file_id"],
    )
    op.create_index(
        "ix_knowledge_connector_sync_items_status",
        "knowledge_connector_sync_items",
        ["status"],
    )
    op.create_index(
        "ix_knowledge_connector_sync_items_deleted_at",
        "knowledge_connector_sync_items",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_connector_sync_items_deleted_at", table_name="knowledge_connector_sync_items")
    op.drop_index("ix_knowledge_connector_sync_items_status", table_name="knowledge_connector_sync_items")
    op.drop_index("ix_knowledge_connector_sync_items_source_file_id", table_name="knowledge_connector_sync_items")
    op.drop_index("ix_knowledge_connector_sync_items_source_object_id", table_name="knowledge_connector_sync_items")
    op.drop_index("ix_knowledge_connector_sync_items_sync_run_id", table_name="knowledge_connector_sync_items")
    op.drop_table("knowledge_connector_sync_items")

    op.drop_index("ix_knowledge_connector_sync_runs_deleted_at", table_name="knowledge_connector_sync_runs")
    op.drop_index("ix_knowledge_connector_sync_runs_status", table_name="knowledge_connector_sync_runs")
    op.drop_index("ix_knowledge_connector_sync_runs_connector_id", table_name="knowledge_connector_sync_runs")
    op.drop_table("knowledge_connector_sync_runs")

    op.drop_index("uq_connector_source_object_ext", table_name="knowledge_connector_source_objects")
    op.drop_index("ix_knowledge_connector_source_objects_deleted_at", table_name="knowledge_connector_source_objects")
    op.drop_index(
        "ix_knowledge_connector_source_objects_source_file_id",
        table_name="knowledge_connector_source_objects",
    )
    op.drop_index(
        "ix_knowledge_connector_source_objects_connector_id",
        table_name="knowledge_connector_source_objects",
    )
    op.drop_table("knowledge_connector_source_objects")

    op.drop_index("uq_connector_credential_connector_id", table_name="knowledge_connector_credentials")
    op.drop_index("ix_knowledge_connector_credentials_deleted_at", table_name="knowledge_connector_credentials")
    op.drop_index("ix_knowledge_connector_credentials_connector_id", table_name="knowledge_connector_credentials")
    op.drop_table("knowledge_connector_credentials")

    op.drop_index("uq_connector_org_kb_name", table_name="knowledge_source_connectors")
    op.drop_index("ix_knowledge_source_connectors_deleted_at", table_name="knowledge_source_connectors")
    op.drop_index("ix_knowledge_source_connectors_knowledge_base_id", table_name="knowledge_source_connectors")
    op.drop_index("ix_knowledge_source_connectors_org_id", table_name="knowledge_source_connectors")
    op.drop_table("knowledge_source_connectors")

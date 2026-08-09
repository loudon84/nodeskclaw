"""Connector domain ORM models."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, LargeBinary, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class KnowledgeSourceConnector(BaseModel):
    __tablename__ = "knowledge_source_connectors"
    __table_args__ = (
        Index(
            "uq_connector_org_kb_name",
            "org_id",
            "knowledge_base_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    knowledge_base_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="provisioning")
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    credential_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    owner_member_id: Mapped[str] = mapped_column(String(36), nullable=False)
    sync_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    sync_interval_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sync_cursor: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    last_sync_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_succeeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ConnectorCredential(BaseModel):
    __tablename__ = "knowledge_connector_credentials"
    __table_args__ = (
        Index(
            "uq_connector_credential_connector_id",
            "connector_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    connector_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_by_member_id: Mapped[str] = mapped_column(String(36), nullable=False)


class ConnectorSourceObject(BaseModel):
    __tablename__ = "knowledge_connector_source_objects"
    __table_args__ = (
        Index(
            "uq_connector_source_object_ext",
            "connector_id",
            "external_object_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    connector_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    external_object_id: Mapped[str] = mapped_column(String(512), nullable=False)
    source_file_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    canonical_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_revision: Mapped[str | None] = mapped_column(String(256), nullable=True)
    etag: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    last_seen_sync_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ConnectorSyncRun(BaseModel):
    __tablename__ = "knowledge_connector_sync_runs"

    connector_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    cursor_before: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    cursor_after: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_member_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class ConnectorSyncItem(BaseModel):
    __tablename__ = "knowledge_connector_sync_items"

    sync_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_object_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    source_file_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    ingestion_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

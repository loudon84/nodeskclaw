"""SourceFile ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


# @lat: [[knowledge-objects#Source File]]
class SourceFile(BaseModel):
    __tablename__ = "source_files"
    __table_args__ = (
        Index(
            "uq_source_file_kb_name_manual",
            "knowledge_base_id",
            "file_name",
            unique=True,
            postgresql_where=text("connector_id IS NULL AND deleted_at IS NULL"),
        ),
        Index(
            "uq_source_file_connector_object",
            "connector_id",
            "external_object_id",
            unique=True,
            postgresql_where=text("connector_id IS NOT NULL AND deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    knowledge_base_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    owner_member_id: Mapped[str] = mapped_column(String(36), nullable=False)
    active_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    acl_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    metadata_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    connector_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    external_object_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_revision: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source_etag: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    archive_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

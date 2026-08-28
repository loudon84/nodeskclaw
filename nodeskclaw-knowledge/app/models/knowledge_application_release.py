"""KnowledgeApplicationRelease and KnowledgeReleaseChannel ORM models."""

# @lat: [[knowledge-objects#Application Release]]
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class KnowledgeApplicationRelease(BaseModel):
    __tablename__ = "knowledge_application_releases"
    __table_args__ = (
        Index(
            "uq_application_release_version",
            "application_id",
            "version",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    release_manifest: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    manifest_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quality_snapshot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    validation_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by_member_id: Mapped[str] = mapped_column(String(36), nullable=False)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validation_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class KnowledgeReleaseChannel(BaseModel):
    __tablename__ = "knowledge_release_channels"
    __table_args__ = (
        Index(
            "uq_release_channel_app_name",
            "application_id",
            "channel",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    active_release_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    traffic_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    updated_by_member_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class KnowledgeReleaseChannelEvent(BaseModel):
    __tablename__ = "knowledge_release_channel_events"
    __table_args__ = (
        Index(
            "ix_release_channel_event_app_channel",
            "application_id",
            "channel",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    from_release_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    to_release_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_member_id: Mapped[str] = mapped_column(String(36), nullable=False)

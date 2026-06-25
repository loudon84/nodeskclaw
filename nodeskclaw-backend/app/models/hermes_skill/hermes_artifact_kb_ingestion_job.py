import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class HermesArtifactKbIngestionJob(BaseModel):
    __tablename__ = "hermes_artifact_kb_ingestion_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    artifact_id: Mapped[str] = mapped_column(String(36), ForeignKey("hermes_artifacts.id", ondelete="CASCADE"), nullable=False)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("hermes_tasks.id", ondelete="CASCADE"), nullable=False)
    knowledge_base: Mapped[str] = mapped_column(String(128), nullable=False, default="general")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_review")
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    index_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_hermes_kb_jobs_org_status", "org_id", "status"),
        Index("ix_hermes_kb_jobs_artifact", "artifact_id"),
        Index("ix_hermes_kb_jobs_task", "task_id"),
        Index(
            "ix_hermes_kb_jobs_sha256_org",
            "org_id", "sha256",
            postgresql_where=text("deleted_at IS NULL AND sha256 IS NOT NULL"),
        ),
    )

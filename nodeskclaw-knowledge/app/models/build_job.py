"""KnowledgeBuildJob ORM — separate from IngestionJob."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


# @lat: [[knowledge-objects#Build Job]]
class KnowledgeBuildJob(BaseModel):
    __tablename__ = "knowledge_build_jobs"
    __table_args__ = (
        Index(
            "uq_build_job_active_kb_index",
            "knowledge_base_id",
            "index_type",
            unique=True,
            postgresql_where=text(
                "deleted_at IS NULL AND status IN ('queued', 'running')"
            ),
        ),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    knowledge_base_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    build_profile_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    index_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_manifest_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trigger_reason: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stage_results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by_member_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

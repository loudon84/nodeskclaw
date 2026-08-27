"""IndexState ORM — per KB × index_type lifecycle state."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.enums import IndexRetrievalStatus


# @lat: [[knowledge-objects#Index State]]
class IndexState(BaseModel):
    __tablename__ = "knowledge_index_states"
    __table_args__ = (
        Index(
            "uq_index_state_kb_type",
            "knowledge_base_id",
            "index_type",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    knowledge_base_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    index_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_built")
    retrieval_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=IndexRetrievalStatus.unavailable.value,
    )
    build_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_watermark: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_build_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    runtime_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validation_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    coverage_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_built_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

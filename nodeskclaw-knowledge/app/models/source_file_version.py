"""SourceFileVersion ORM model."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


# @lat: [[knowledge-objects#Source File]]
class SourceFileVersion(BaseModel):
    __tablename__ = "source_file_versions"
    __table_args__ = (
        Index(
            "uq_sfv_source_version",
            "source_file_id",
            "version_no",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_sfv_ragflow_document",
            "ragflow_document_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND ragflow_document_id IS NOT NULL"),
        ),
    )

    source_file_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    ragflow_document_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uploaded_by_member_id: Mapped[str] = mapped_column(String(36), nullable=False)
    ragflow_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    parse_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ragflow_run: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ragflow_progress: Mapped[float | None] = mapped_column(Float, nullable=True)
    ragflow_progress_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    process_duration: Mapped[float | None] = mapped_column(Float, nullable=True)

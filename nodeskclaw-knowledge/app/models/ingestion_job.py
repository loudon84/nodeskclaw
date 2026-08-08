"""IngestionJob ORM model."""

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class IngestionJob(BaseModel):
    __tablename__ = "knowledge_ingestion_jobs"

    source_file_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    file_version_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    ragflow_document_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by_member_id: Mapped[str] = mapped_column(String(36), nullable=False)

"""Translation Document / Page / Revision ORM models."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class TranslationDocument(BaseModel):
    __tablename__ = "knowledge_translation_documents"
    __table_args__ = (
        Index(
            "uq_translation_doc_source_lang",
            "source_file_id",
            "file_version_id",
            "target_lang",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_file_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    file_version_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    target_lang: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by_member_id: Mapped[str] = mapped_column(String(36), nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class TranslationPage(BaseModel):
    __tablename__ = "knowledge_translation_pages"
    __table_args__ = (
        Index(
            "uq_translation_page",
            "document_id",
            "page_no",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    document_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    artifact_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class TranslationRevision(BaseModel):
    __tablename__ = "knowledge_translation_revisions"
    __table_args__ = (
        Index(
            "uq_translation_revision",
            "page_id",
            "revision",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    page_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    artifact_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_by_member_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class TranslationJob(BaseModel):
    __tablename__ = "knowledge_translation_jobs"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    page_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

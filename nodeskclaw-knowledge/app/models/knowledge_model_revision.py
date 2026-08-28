"""KnowledgeModelRevision ORM — immutable semantic model revisions."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class KnowledgeModelRevision(BaseModel):
    __tablename__ = "knowledge_model_revisions"
    __table_args__ = (
        Index(
            "uq_knowledge_model_revision_model_version",
            "knowledge_model_id",
            "revision_number",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_knowledge_model_revision_single_active",
            "knowledge_model_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND status = 'active'"),
        ),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    knowledge_model_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entities: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    relations: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    terms: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    extraction_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by_member_id: Mapped[str] = mapped_column(String(36), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

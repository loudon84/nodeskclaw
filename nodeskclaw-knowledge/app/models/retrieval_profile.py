"""RetrievalProfile ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.enums import DEFAULT_RETRIEVAL_CONFIG


# @lat: [[knowledge-objects#Retrieval Profile]]
class RetrievalProfile(BaseModel):
    __tablename__ = "knowledge_retrieval_profiles"
    __table_args__ = (
        Index(
            "uq_retrieval_profile_set_version",
            "knowledge_set_id",
            "version",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND scope_type = 'set'"),
        ),
        Index(
            "uq_retrieval_profile_application_version",
            "application_id",
            "version",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND scope_type = 'application'"),
        ),
    )

    knowledge_set_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    application_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, default="set")
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=lambda: dict(DEFAULT_RETRIEVAL_CONFIG)
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_by_member_id: Mapped[str] = mapped_column(String(36), nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

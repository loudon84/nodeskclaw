"""KnowledgeSet ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.models.enums import DEFAULT_RETRIEVAL_CONFIG


# @lat: [[knowledge-objects#Knowledge Set]]
class KnowledgeSet(BaseModel):
    __tablename__ = "knowledge_sets"
    __table_args__ = (
        Index(
            "uq_ks_org_name",
            "org_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_member_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    acl_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    retrieval_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=lambda: dict(DEFAULT_RETRIEVAL_CONFIG)
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="private")

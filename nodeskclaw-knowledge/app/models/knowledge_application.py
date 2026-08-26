"""KnowledgeApplication ORM — product-facing retrieval/chat surface."""

from sqlalchemy import Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


# @lat: [[knowledge-objects#Knowledge Application]]
class KnowledgeApplication(BaseModel):
    __tablename__ = "knowledge_applications"
    __table_args__ = (
        Index(
            "uq_knowledge_application_org_name",
            "org_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_member_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    answer_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    active_profile_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    acl_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="private")
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class KnowledgeApplicationSetItem(BaseModel):
    __tablename__ = "knowledge_application_set_items"
    __table_args__ = (
        Index(
            "uq_application_set_item",
            "application_id",
            "knowledge_set_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    application_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    knowledge_set_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

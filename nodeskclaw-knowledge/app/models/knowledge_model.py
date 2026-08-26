"""KnowledgeModel ORM — entity/relation/term/extraction_policy JSON catalog."""

from sqlalchemy import Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


# @lat: [[knowledge-objects#Knowledge Model]]
class KnowledgeModel(BaseModel):
    __tablename__ = "knowledge_models"
    __table_args__ = (
        Index(
            "uq_knowledge_model_org_name",
            "org_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    entities: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    relations: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    terms: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    extraction_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by_member_id: Mapped[str] = mapped_column(String(36), nullable=False)

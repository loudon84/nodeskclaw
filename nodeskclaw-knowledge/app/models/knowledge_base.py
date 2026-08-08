"""KnowledgeBase ORM model."""

from sqlalchemy import Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class KnowledgeBase(BaseModel):
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        Index(
            "uq_kb_org_name",
            "org_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_kb_ragflow_dataset",
            "ragflow_dataset_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND ragflow_dataset_id IS NOT NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ragflow_dataset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False, default="bge-m3")
    chunk_method: Mapped[str] = mapped_column(String(64), nullable=False, default="naive")
    parser_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    owner_member_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="provisioning")

"""KnowledgeSetItem ORM model."""

from decimal import Decimal

from sqlalchemy import Index, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class KnowledgeSetItem(BaseModel):
    __tablename__ = "knowledge_set_items"
    __table_args__ = (
        Index(
            "uq_ks_item",
            "knowledge_set_id",
            "knowledge_base_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    knowledge_set_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    knowledge_base_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    weight: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, default=Decimal("1.0"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

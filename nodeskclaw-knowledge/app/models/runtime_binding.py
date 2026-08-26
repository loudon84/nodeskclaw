"""KnowledgeRuntimeBinding ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


# @lat: [[knowledge-objects#Runtime Binding]]
class KnowledgeRuntimeBinding(BaseModel):
    __tablename__ = "knowledge_runtime_bindings"
    __table_args__ = (
        Index(
            "uq_runtime_binding_kb_type",
            "knowledge_base_id",
            "runtime_type",
            "resource_type",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_runtime_binding_resource",
            "runtime_type",
            "resource_type",
            "resource_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    knowledge_base_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    runtime_type: Mapped[str] = mapped_column(String(32), nullable=False, default="ragflow")
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False, default="dataset")
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)
    runtime_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ready")
    capabilities: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    runtime_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

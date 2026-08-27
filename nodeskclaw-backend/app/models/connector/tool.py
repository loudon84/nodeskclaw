from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ConnectorTool(BaseModel):
    __tablename__ = "connector_tools"
    __table_args__ = (
        Index(
            "uq_connector_tools_instance_name",
            "instance_id",
            "tool_name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_connector_tools_org_public",
            "org_id",
            "is_public",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    instance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("connector_instances.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    extra_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

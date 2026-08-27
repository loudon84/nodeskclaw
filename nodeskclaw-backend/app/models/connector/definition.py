from __future__ import annotations

import enum

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ConnectorKind(str, enum.Enum):
    MCP = "mcp"
    REST = "rest"
    DB = "db"


class ConnectorDefinition(BaseModel):
    __tablename__ = "connector_definitions"
    __table_args__ = (
        Index(
            "uq_connector_definitions_org_name",
            "org_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_connector_definitions_org_kind",
            "org_id",
            "kind",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

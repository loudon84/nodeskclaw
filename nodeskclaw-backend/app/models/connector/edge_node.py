from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class EdgeNodeStatus(str, enum.Enum):
    PENDING = "pending"
    ONLINE = "online"
    STALE = "stale"
    DISABLED = "disabled"


class EdgeNode(BaseModel):
    __tablename__ = "edge_nodes"
    __table_args__ = (
        Index(
            "uq_edge_nodes_org_name",
            "org_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=EdgeNodeStatus.PENDING.value)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EdgeControlNonce(Base):
    """Append-only request nonce ledger. No soft delete."""

    __tablename__ = "edge_control_nonces"
    __table_args__ = (
        Index(
            "uq_edge_control_nonces_node_identity_nonce",
            "node_id",
            "identity_version",
            "nonce",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    node_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("edge_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identity_version: Mapped[int] = mapped_column(Integer, nullable=False)
    nonce: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

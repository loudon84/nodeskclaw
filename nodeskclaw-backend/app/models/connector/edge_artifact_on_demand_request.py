from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class OnDemandRequestStatus(str, enum.Enum):
    ISSUED = "issued"
    CONSUMED = "consumed"
    EXPIRED = "expired"


class EdgeArtifactOnDemandRequest(BaseModel):
    __tablename__ = "edge_artifact_on_demand_requests"
    __table_args__ = (
        Index(
            "uq_edge_artifact_on_demand_req",
            "org_id",
            "job_id",
            "name",
            "run_generation",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_edge_artifact_on_demand_node_status",
            "edge_node_id",
            "status",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    edge_node_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("edge_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("edge_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    attempt_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    step_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    run_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    delivery_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    artifact_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=OnDemandRequestStatus.ISSUED.value)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

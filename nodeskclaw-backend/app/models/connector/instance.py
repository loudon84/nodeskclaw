from __future__ import annotations

import enum

from sqlalchemy import Boolean, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ConnectorPlacement(str, enum.Enum):
    CENTRAL = "central"
    EDGE = "edge"


class ConnectorInstance(BaseModel):
    __tablename__ = "connector_instances"
    __table_args__ = (
        Index(
            "uq_connector_instances_def_name",
            "definition_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_connector_instances_org_placement",
            "org_id",
            "placement",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    definition_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("connector_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    placement: Mapped[str] = mapped_column(String(32), nullable=False, default=ConnectorPlacement.CENTRAL.value)
    edge_node_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("edge_nodes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    secret_ref_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("secret_refs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

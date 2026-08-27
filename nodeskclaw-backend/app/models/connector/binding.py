from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class SkillConnectorBinding(BaseModel):
    __tablename__ = "skill_connector_bindings"
    __table_args__ = (
        Index(
            "uq_skill_connector_bindings_release_instance",
            "skill_release_id",
            "connector_instance_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_release_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("hermes_skill_releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    connector_instance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("connector_instances.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str | None] = mapped_column(String(64), nullable=True)

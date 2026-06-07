import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ArtifactPermission(BaseModel):
    __tablename__ = "artifact_permissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    artifact_id: Mapped[str] = mapped_column(String(36), ForeignKey("hermes_artifacts.id", ondelete="CASCADE"), nullable=False)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    granted_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    permission_level: Mapped[str] = mapped_column(String(32), nullable=False, default="viewer")
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_ap_artifact_id", "artifact_id"),
        Index("ix_ap_user_id", "user_id"),
        Index(
            "uq_ap_artifact_user_alive", "artifact_id", "user_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_artifact_permissions_org_user",
            "org_id", "user_id",
            postgresql_where=text("deleted_at IS NULL AND revoked_at IS NULL"),
        ),
    )

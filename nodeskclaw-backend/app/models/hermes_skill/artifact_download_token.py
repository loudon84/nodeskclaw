import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ArtifactDownloadToken(BaseModel):
    __tablename__ = "artifact_download_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    artifact_id: Mapped[str] = mapped_column(String(36), ForeignKey("hermes_artifacts.id", ondelete="CASCADE"), nullable=False)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    uses_remaining: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("ix_adt_artifact_id", "artifact_id"),
        Index("ix_adt_org_id", "org_id"),
        Index(
            "uq_adt_token_alive", "token",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

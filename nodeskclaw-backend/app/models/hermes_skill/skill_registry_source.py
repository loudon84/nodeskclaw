from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class HermesSkillRegistry(BaseModel):
    __tablename__ = "hermes_skill_registries"
    __table_args__ = (
        Index(
            "ix_hermes_skill_reg_name_org_unique",
            "name", "org_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    auth_secret_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[str] = mapped_column(String(32), nullable=False, default="never")
    last_sync_error: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    cache_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    cache_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_modified: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

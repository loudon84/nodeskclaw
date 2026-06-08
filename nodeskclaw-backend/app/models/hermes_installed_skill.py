"""Installed Hermes skills on desktop profiles."""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class InstalledSkillStatus(str, Enum):
    installed = "installed"
    update_available = "update_available"
    uninstalled = "uninstalled"
    missing = "missing"
    failed = "failed"


class HermesInstalledSkill(BaseModel):
    __tablename__ = "hermes_installed_skills"
    __table_args__ = (
        Index(
            "uq_hermes_installed_skills_profile_slug_active",
            "profile_id",
            "gene_slug",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_hermes_installed_skills_user",
            "org_id",
            "user_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    desktop_device_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("desktop_devices.id"), nullable=False
    )
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("desktop_hermes_profiles.id"), nullable=False
    )
    gene_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("genes.id"), nullable=True
    )
    gene_slug: Mapped[str] = mapped_column(String(128), nullable=False)
    gene_version: Mapped[str] = mapped_column(String(32), nullable=False)
    skill_name: Mapped[str] = mapped_column(String(128), nullable=False)
    install_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default=InstalledSkillStatus.installed, nullable=False
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    installed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

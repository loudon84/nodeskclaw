"""Hermes profile on a desktop device."""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ProfileStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    error = "error"


class DesktopHermesProfile(BaseModel):
    __tablename__ = "desktop_hermes_profiles"
    __table_args__ = (
        Index(
            "uq_desktop_hermes_profiles_device_profile_active",
            "desktop_device_id",
            "profile_name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_desktop_hermes_profiles_user",
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
    profile_name: Mapped[str] = mapped_column(String(128), nullable=False)
    hermes_home: Mapped[str] = mapped_column(Text, nullable=False)
    runtime_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gateway_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    gateway_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default=ProfileStatus.active, nullable=False
    )
    capabilities: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

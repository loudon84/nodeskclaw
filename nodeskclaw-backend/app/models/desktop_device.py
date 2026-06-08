"""Desktop device registration for GeneHub."""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class DeviceStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    blocked = "blocked"


class DesktopDevice(BaseModel):
    __tablename__ = "desktop_devices"
    __table_args__ = (
        Index(
            "uq_desktop_devices_user_fingerprint_active",
            "user_id",
            "device_fingerprint",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_desktop_devices_org_user",
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
    device_name: Mapped[str] = mapped_column(String(128), nullable=False)
    device_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    os_type: Mapped[str] = mapped_column(String(32), nullable=False)
    os_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default=DeviceStatus.active, nullable=False
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

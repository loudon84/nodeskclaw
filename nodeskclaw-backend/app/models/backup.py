"""Instance backup model for disaster recovery."""

from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class BackupStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"


class BackupType(str, Enum):
    manual = "manual"
    pre_upgrade = "pre_upgrade"


class InstanceBackup(BaseModel):
    __tablename__ = "instance_backups"

    instance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("instances.id"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(
        String(16), default=BackupType.manual, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), default=BackupStatus.pending, nullable=False
    )
    config_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    data_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    org_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=True, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    instance = relationship("Instance", foreign_keys=[instance_id])
    user = relationship("User", foreign_keys=[triggered_by])

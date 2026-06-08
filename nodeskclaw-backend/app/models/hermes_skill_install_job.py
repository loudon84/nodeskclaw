"""Hermes desktop skill install jobs."""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class InstallJobType(str, Enum):
    install = "install"
    update = "update"
    uninstall = "uninstall"
    rollback = "rollback"


class InstallJobStatus(str, Enum):
    pending = "pending"
    claimed = "claimed"
    downloading = "downloading"
    validating = "validating"
    installing = "installing"
    installed = "installed"
    failed = "failed"
    cancelled = "cancelled"
    superseded = "superseded"


class InstallMode(str, Enum):
    assigned = "assigned"
    self_service = "self_service"


ACTIVE_JOB_STATUSES = frozenset({
    InstallJobStatus.pending,
    InstallJobStatus.claimed,
    InstallJobStatus.downloading,
    InstallJobStatus.validating,
    InstallJobStatus.installing,
})


class HermesSkillInstallJob(BaseModel):
    __tablename__ = "hermes_skill_install_jobs"
    __table_args__ = (
        Index(
            "ix_hermes_install_jobs_user_status",
            "org_id",
            "user_id",
            "status",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_hermes_install_jobs_profile_status",
            "profile_id",
            "status",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_hermes_install_jobs_gene",
            "gene_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    desktop_device_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("desktop_devices.id"), nullable=True
    )
    profile_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("desktop_hermes_profiles.id"), nullable=True
    )
    gene_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("genes.id"), nullable=False
    )
    gene_slug: Mapped[str] = mapped_column(String(128), nullable=False)
    gene_version: Mapped[str] = mapped_column(String(32), nullable=False)
    skill_name: Mapped[str] = mapped_column(String(128), nullable=False)
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    install_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    manifest_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bundle_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    requested_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

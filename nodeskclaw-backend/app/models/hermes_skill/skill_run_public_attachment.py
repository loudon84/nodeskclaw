from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


# @lat: [[architecture/skill-agent#RM-18 Public Attachment Input]]
class SkillRunPublicAttachment(BaseModel):
    __tablename__ = "skill_run_public_attachments"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    attachment_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scan_status: Mapped[str] = mapped_column(String(32), nullable=False)
    scan_reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "uq_skill_run_public_attachments_ref_alive",
            "attachment_ref",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_skill_run_public_attachments_org_user_ref",
            "org_id",
            "user_id",
            "attachment_ref",
        ),
    )

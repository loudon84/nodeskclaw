import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class SkillReleaseStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class HermesSkillRelease(BaseModel):
    __tablename__ = "hermes_skill_releases"
    __table_args__ = (
        Index(
            "uq_hermes_skill_releases_skill_version",
            "skill_db_id",
            "version",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_hermes_skill_releases_one_published",
            "skill_db_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND status = 'published'"),
        ),
        Index(
            "ix_hermes_skill_releases_org_skill",
            "org_id",
            "skill_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_hermes_skill_releases_org_status",
            "org_id",
            "status",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_db_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("hermes_skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id: Mapped[str] = mapped_column(String(255), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=SkillReleaseStatus.DRAFT.value)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    bundle_ref: Mapped[str | None] = mapped_column(String(36), nullable=True)
    bundle_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bundle_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extra_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    requirements: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

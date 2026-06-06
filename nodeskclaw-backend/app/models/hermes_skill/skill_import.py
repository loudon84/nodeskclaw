from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class HermesSkillImport(BaseModel):
    __tablename__ = "hermes_skill_imports"
    __table_args__ = (
        Index("ix_hermes_skill_imports_org", "org_id"),
        Index("ix_hermes_skill_imports_status", "status"),
    )

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="github")
    target_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    conflict_strategy: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="preview")
    total_skills: Mapped[int] = mapped_column(default=0, nullable=False)
    imported_skills: Mapped[int] = mapped_column(default=0, nullable=False)
    failed_skills: Mapped[int] = mapped_column(default=0, nullable=False)
    skipped_skills: Mapped[int] = mapped_column(default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

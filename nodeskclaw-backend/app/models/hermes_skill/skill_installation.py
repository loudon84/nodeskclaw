from sqlalchemy import Boolean, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from datetime import datetime


class HermesSkillInstallation(BaseModel):
    __tablename__ = "hermes_skill_installations"
    __table_args__ = (
        Index(
            "ix_hermes_skill_inst_skill_agent_unique",
            "skill_id", "agent_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_hermes_skill_inst_org", "org_id"),
        Index("ix_hermes_skill_inst_status", "status"),
    )

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    profile_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    workspace_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    install_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="copy")
    installed_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    installed_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    link_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    symlink_target: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    installed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    target_agent_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    conflict_strategy: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(nullable=True)
    install_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

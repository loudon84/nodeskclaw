from sqlalchemy import Boolean, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class HermesSkill(BaseModel):
    __tablename__ = "hermes_skills"
    __table_args__ = (
        Index(
            "ix_hermes_skills_skill_id_org_unique",
            "skill_id", "org_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_hermes_skills_tool_name_org_unique",
            "tool_name", "org_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_hermes_skills_canonical_path_org_unique",
            "canonical_path", "org_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_hermes_skills_org_source", "org_id", "source_type"),
        Index("ix_hermes_skills_org_agent_type", "org_id", "agent_type"),
    )

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id: Mapped[str] = mapped_column(String(255), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    agent_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    runtime: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="central")
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    canonical_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    relative_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_central: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_read_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_mcp_exposed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    manifest_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    gateway_manifest_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    input_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    extra_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    scanned_at: Mapped[str | None] = mapped_column(String(32), nullable=True)

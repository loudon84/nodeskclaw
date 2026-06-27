from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ExpertSkill(BaseModel):
    __tablename__ = "expert_skills"

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    expert_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("experts.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    skill_name: Mapped[str] = mapped_column(String(128), nullable=False)
    upstream_tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    call_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, default="low")
    approval_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="server")
    output_formats: Mapped[list] = mapped_column(JSONB, nullable=False, server_default='["markdown"]')
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        Index(
            "uq_expert_skill_org_expert_skill_name",
            "org_id", "expert_id", "skill_name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_expert_skill_org_expert_upstream",
            "org_id", "expert_id", "upstream_tool_name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

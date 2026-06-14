from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class McpToolGrant(BaseModel):
    __tablename__ = "mcp_tool_grants"
    __table_args__ = (
        Index(
            "uq_mcp_tool_grants_active",
            "org_id",
            "user_id",
            "instance_id",
            "tool_name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND grant_status = 'active'"),
        ),
        Index("ix_mcp_tool_grants_org_status", "org_id", "grant_status"),
        Index("ix_mcp_tool_grants_user", "user_id"),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    desktop_device_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    profile_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    profile_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    instance_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(200), nullable=False)
    permission: Mapped[str] = mapped_column(String(20), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    grant_status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    approved_by: Mapped[str] = mapped_column(String(36), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    constraints_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source_request_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

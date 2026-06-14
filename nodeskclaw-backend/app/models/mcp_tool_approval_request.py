from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class McpToolApprovalRequest(BaseModel):
    __tablename__ = "mcp_tool_approval_requests"
    __table_args__ = (
        Index("ix_mcp_tool_approval_requests_org_status", "org_id", "status"),
        Index("ix_mcp_tool_approval_requests_requester", "requester_user_id"),
        Index("ix_mcp_tool_approval_requests_tool", "tool_name"),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    requester_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    desktop_device_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    profile_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    profile_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    instance_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    instance_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(200), nullable=False)
    permission: Mapped[str] = mapped_column(String(20), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    request_source: Mapped[str] = mapped_column(String(50), nullable=False)
    request_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    arguments_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    grant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

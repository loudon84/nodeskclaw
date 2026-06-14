from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class McpToolPolicyEvent(BaseModel):
    __tablename__ = "mcp_tool_policy_events"
    __table_args__ = (
        Index("ix_mcp_tool_policy_events_org_created", "org_id", "created_at"),
        Index("ix_mcp_tool_policy_events_tool", "tool_name"),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    target_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(200), nullable=False)
    instance_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    approval_request_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    grant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    before_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

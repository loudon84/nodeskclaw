"""MCP Skill Gateway call audit log."""

from sqlalchemy import Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class McpCallLog(BaseModel):
    __tablename__ = "mcp_call_logs"
    __table_args__ = (
        Index("ix_mcp_call_logs_org_created", "org_id", "created_at"),
        Index("ix_mcp_call_logs_user_created", "user_id", "created_at"),
        Index("ix_mcp_call_logs_tool_created", "tool_name", "created_at"),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    instance_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

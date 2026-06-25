from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class HermesMcpRouterSyncLog(BaseModel):
    __tablename__ = "hermes_mcp_router_sync_logs"
    __table_args__ = (
        Index("ix_hermes_mcp_router_sync_logs_org_agent", "org_id", "agent_id"),
        Index("ix_hermes_mcp_router_sync_logs_created_at", "created_at"),
    )

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False,
    )
    agent_id: Mapped[str] = mapped_column(String(36), nullable=False)
    instance_name: Mapped[str] = mapped_column(String(128), nullable=False)
    profile: Mapped[str] = mapped_column(String(128), nullable=False, default="default")
    mcp_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    router_skill_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    router_skill_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_snapshot: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class McpClientToken(BaseModel):
    __tablename__ = "mcp_client_tokens"
    __table_args__ = (
        Index(
            "uq_mcp_client_tokens_active_agent",
            "hermes_agent_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND revoked_at IS NULL"),
        ),
        Index("ix_mcp_client_tokens_org", "org_id"),
        Index("ix_mcp_client_tokens_prefix", "token_prefix"),
        Index("ix_mcp_client_tokens_hash", "token_hash"),
    )

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(64), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False, default="mcp_client")
    service_account_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    hermes_agent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("hermes_agent_instances.id", ondelete="SET NULL"), nullable=True,
    )
    hermes_instance_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    profile: Mapped[str] = mapped_column(String(128), nullable=False, default="default")
    workspace_id: Mapped[str] = mapped_column(String(128), nullable=False, default="default")
    scopes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    allowed_tools: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    allowed_skills: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    constraints_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)

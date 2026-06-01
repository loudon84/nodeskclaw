"""Agent file access grants for stable download URLs."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AgentFileAccessGrant(BaseModel):
    __tablename__ = "agent_file_access_grants"
    __table_args__ = (
        Index(
            "uq_agent_file_grants_active",
            "file_reference_id",
            "recipient_agent_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND revoked_at IS NULL"),
        ),
        Index(
            "ix_agent_file_grants_recipient",
            "workspace_id",
            "recipient_agent_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_agent_file_grants_source",
            "workspace_id",
            "source",
            "file_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspace_messages.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    file_reference_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspace_message_file_references.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    recipient_agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("instances.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    file_id: Mapped[str] = mapped_column(String(36), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    permissions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    access_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

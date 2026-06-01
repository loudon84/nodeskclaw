"""Workspace message file reference snapshots."""

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class WorkspaceMessageFileReference(BaseModel):
    __tablename__ = "workspace_message_file_references"
    __table_args__ = (
        Index(
            "uq_workspace_msg_file_ref_active",
            "message_id",
            "source",
            "file_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_workspace_msg_file_ref_source",
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
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    file_id: Mapped[str] = mapped_column(String(36), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    scan_status: Mapped[str] = mapped_column(String(32), default="skipped", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="available", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

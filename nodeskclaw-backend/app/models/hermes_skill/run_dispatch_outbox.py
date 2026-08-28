from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class RunDispatchStatus(str, enum.Enum):
    PENDING = "pending"
    DELIVERING = "delivering"
    DELIVERED = "delivered"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"


class RunDispatchOutbox(BaseModel):
    __tablename__ = "run_dispatch_outbox"

    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hermes_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dispatch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=RunDispatchStatus.PENDING.value,
        index=True,
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    command_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dispatcher_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index(
            "uq_run_dispatch_outbox_dispatch_id_alive",
            "org_id",
            "dispatch_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_run_dispatch_outbox_pending_poll",
            "status",
            "next_retry_at",
            "created_at",
            postgresql_where=text("deleted_at IS NULL AND (status = 'pending' OR status = 'delivering')"),
        ),
    )

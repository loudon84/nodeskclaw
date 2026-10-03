from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class IntegrationConnectAttempt(BaseModel):
    __tablename__ = "integration_connect_attempts"
    __table_args__ = (
        Index("ix_integration_connect_attempts_account", "integration_account_id"),
    )

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    initiated_by_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    owner_type: Mapped[str] = mapped_column(String(32), nullable=False, default="USER")
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    integration_account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("integration_accounts.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    toolkit_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    baseline_account_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_connected_account_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

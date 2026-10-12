"""One desktop OAuth login attempt. Casdoor tokens are never stored here."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class OAuthLoginTransaction(BaseModel):
    __tablename__ = "oauth_login_transaction"
    __table_args__ = (
        Index(
            "uq_oauth_login_transaction_state",
            "state",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_oauth_login_transaction_exchange",
            "exchange_code_hash",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND exchange_code_hash IS NOT NULL"),
        ),
    )

    state: Mapped[str] = mapped_column(String(128), nullable=False)
    code_verifier: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    return_to: Mapped[str] = mapped_column(String(256), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exchange_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exchange_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exchange_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    member_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

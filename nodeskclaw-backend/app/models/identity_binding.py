"""Casdoor subject bound to an existing member."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class IdentityBinding(BaseModel):
    __tablename__ = "identity_binding"
    __table_args__ = (
        Index(
            "uq_identity_binding_provider_subject",
            "provider",
            "provider_org",
            "provider_user_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_identity_binding_casdoor_member",
            "member_user_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND provider = 'casdoor'"),
        ),
    )

    member_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_org: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(256), nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

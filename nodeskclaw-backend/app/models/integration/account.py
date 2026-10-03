from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel

OWNER_TYPE_USER = "USER"
OWNER_TYPE_ORGANIZATION = "ORGANIZATION"


class IntegrationAccount(BaseModel):
    __tablename__ = "integration_accounts"
    __table_args__ = (
        Index(
            "uq_integration_accounts_owner_provider_account",
            "org_id",
            "owner_type",
            "owner_id",
            "provider",
            "connected_account_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_integration_accounts_shared_authorizing",
            "org_id",
            "provider",
            "toolkit_slug",
            unique=True,
            postgresql_where=text(
                "deleted_at IS NULL AND owner_type = 'ORGANIZATION' AND status = 'AUTHORIZING'"
            ),
        ),
    )

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    owner_type: Mapped[str] = mapped_column(String(32), nullable=False, default=OWNER_TYPE_USER)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    toolkit_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(160), nullable=False)
    connected_account_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    auth_config_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    alias: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="AUTHORIZING")
    auth_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

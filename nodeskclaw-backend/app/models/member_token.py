"""Member model credential. One active row per membership and provider."""

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class MemberToken(BaseModel):
    __tablename__ = "member_tokens"
    __table_args__ = (
        Index(
            "uq_member_tokens_member_provider",
            "member_id",
            "provider",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_member_tokens_one_default",
            "member_id",
            unique=True,
            postgresql_where=text("is_default IS TRUE AND deleted_at IS NULL"),
        ),
        Index(
            "uq_member_tokens_new_api_token_name",
            "provider",
            text("lower(token_name)"),
            unique=True,
            postgresql_where=text(
                "provider = 'new-api' AND token_name IS NOT NULL AND deleted_at IS NULL"
            ),
        ),
        Index("ix_member_tokens_external_token_id", "external_token_id"),
    )

    member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("org_memberships.id"), nullable=False, index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="new-api")
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    token_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    models: Mapped[dict] = mapped_column(JSONB, nullable=False)
    provider_group: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_token_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    token_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sync_status: Mapped[str] = mapped_column(String(24), nullable=False, default="manual")
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True,
    )

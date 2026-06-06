from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class McpGatewayApiKey(BaseModel):
    __tablename__ = "mcp_gateway_api_keys"
    __table_args__ = (
        Index(
            "ix_mcp_gateway_api_keys_prefix_org",
            "key_prefix", "org_id",
        ),
    )

    key_prefix: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    key_suffix: Mapped[str] = mapped_column(String(4), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(10), default="active", nullable=False, index=True)
    rate_limit_rpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allowed_scopes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    last_used_at: Mapped[str | None] = mapped_column(String(36), nullable=True)
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization = relationship("Organization")

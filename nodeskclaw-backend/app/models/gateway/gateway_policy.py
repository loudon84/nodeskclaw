from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class McpGatewayPolicy(BaseModel):
    __tablename__ = "mcp_gateway_policies"
    __table_args__ = (
        Index(
            "ix_mcp_gateway_policies_name_org_unique",
            "name", "org_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_mcp_gateway_policies_scope_ref",
            "scope", "scope_ref_id",
        ),
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_ref_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    rate_limit_rpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_connections: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sensitive_tools: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    organization = relationship("Organization")

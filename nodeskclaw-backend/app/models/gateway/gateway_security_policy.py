from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class McpGatewaySecurityPolicy(BaseModel):
    __tablename__ = "mcp_gateway_security_policies"
    __table_args__ = (
        Index(
            "ix_mcp_gateway_sec_policy_org_unique",
            "org_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    method_whitelist: Mapped[list] = mapped_column(
        JSONB, nullable=False,
        default=lambda: ["tools/list", "tools/call", "resources/list", "resources/read", "prompts/list"],
    )
    max_request_body_bytes: Mapped[int] = mapped_column(Integer, default=1048576, nullable=False)
    global_rate_limit_rpm: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    sse_max_connections: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    sse_max_connections_per_instance: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    origin_check_mode: Mapped[str] = mapped_column(String(10), default="relaxed", nullable=False)
    allowed_origins: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    upstream_host_whitelist: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    sensitive_param_names: Mapped[list] = mapped_column(
        JSONB, nullable=False,
        default=lambda: ["password", "token", "secret", "key", "credential", "api_key", "private_key"],
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    organization = relationship("Organization")

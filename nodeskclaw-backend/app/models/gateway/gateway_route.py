from sqlalchemy import Boolean, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class McpGatewayRoute(BaseModel):
    __tablename__ = "mcp_gateway_routes"
    __table_args__ = (
        Index(
            "ix_mcp_gateway_routes_name_org_unique",
            "name", "org_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_mcp_gateway_routes_instance_org",
            "instance_id", "org_id",
        ),
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    instance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("instances.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mcp_server_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    match_tools: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    priority: Mapped[int] = mapped_column(default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    instance = relationship("Instance")
    organization = relationship("Organization")

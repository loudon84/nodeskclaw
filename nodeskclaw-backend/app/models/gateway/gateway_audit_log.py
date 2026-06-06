import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.models.base import Base


class McpGatewayAuditLog(Base):
    __tablename__ = "mcp_gateway_audit_logs"
    __table_args__ = (
        Index("ix_mcp_gateway_audit_logs_instance_created", "instance_id", "created_at"),
        Index("ix_mcp_gateway_audit_logs_user_created", "caller_user_id", "created_at"),
        Index("ix_mcp_gateway_audit_logs_method_created", "method", "created_at"),
        Index("ix_mcp_gateway_audit_logs_security_event", "security_event"),
        Index("ix_mcp_gateway_audit_logs_auth_type", "auth_type"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    caller_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    caller_org_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    instance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("instances.id", ondelete="SET NULL"), nullable=True, index=True
    )
    mcp_server_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    method: Mapped[str] = mapped_column(String(50), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    request_params_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    response_status: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    policy_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_default_policy: Mapped[bool] = mapped_column(default=False, nullable=False)
    caller_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    auth_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    auth_key_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    params_masked: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    security_event: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

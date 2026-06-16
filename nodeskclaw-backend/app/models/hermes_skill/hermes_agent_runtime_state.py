import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AgentRuntimeStatus(str, enum.Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    MAINTENANCE = "maintenance"
    DRAINING = "draining"
    UNHEALTHY = "unhealthy"
    DELETED = "deleted"


class HermesAgentRuntimeState(BaseModel):
    __tablename__ = "hermes_agent_runtime_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(255), nullable=False)
    runtime_status: Mapped[str] = mapped_column(String(32), nullable=False, default=AgentRuntimeStatus.ENABLED.value)
    accepting_tasks: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    max_concurrent_tasks: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    current_running_tasks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_health_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_health_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    maintenance_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        Index(
            "uq_hermes_agent_runtime_org_agent",
            "org_id", "agent_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_hermes_agent_runtime_org_status", "org_id", "runtime_status"),
    )

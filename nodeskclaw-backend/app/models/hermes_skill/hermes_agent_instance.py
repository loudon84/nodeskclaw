import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class HermesAgentInstance(BaseModel):
    __tablename__ = "hermes_agent_instances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False,
    )
    instance_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("instances.id", ondelete="SET NULL"), nullable=True,
    )
    profile_name: Mapped[str] = mapped_column(String(128), nullable=False)
    container_name: Mapped[str] = mapped_column(String(255), nullable=False)
    container_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    image: Mapped[str | None] = mapped_column(String(512), nullable=True)
    docker_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    docker_health: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    host_ip: Mapped[str | None] = mapped_column(String(128), nullable=True)
    webui_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    webui_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    gateway_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gateway_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    gateway_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    gateway_runtime_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    mcp_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    instance_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    env_file: Mapped[str | None] = mapped_column(Text, nullable=True)
    compose_file: Mapped[str | None] = mapped_column(Text, nullable=True)
    compose_project: Mapped[str | None] = mapped_column(String(255), nullable=True)
    managed_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_probe_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "uq_hermes_agent_instance_org_profile",
            "org_id", "profile_name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_hermes_agent_instance_org_container",
            "org_id", "container_name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_hermes_agent_instance_org_runtime", "org_id", "gateway_runtime_status"),
        Index("ix_hermes_agent_instance_instance_id", "instance_id"),
    )

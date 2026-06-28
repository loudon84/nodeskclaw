from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ExpertInvocationLog(BaseModel):
    __tablename__ = "expert_invocation_logs"

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    expert_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    expert_skill_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    expert_team_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    expert_slug: Mapped[str | None] = mapped_column(String(128), nullable=True)
    catalog_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    catalog_slug: Mapped[str | None] = mapped_column(String(128), nullable=True)
    orchestration_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    skill_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    upstream_tool_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_alias: Mapped[str | None] = mapped_column(String(128), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    jsonrpc_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    request_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    request_prompt_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_content_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    response_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    client_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_device_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    parent_invocation_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    invocation_type: Mapped[str] = mapped_column(String(32), nullable=False, default="expert_skill")
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    task_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    artifact_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    hermes_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stream_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (
        Index("ix_expert_invocation_org_created", "org_id", "created_at"),
        Index("ix_expert_invocation_org_expert", "org_id", "expert_id"),
        Index("ix_expert_invocation_org_status", "org_id", "status"),
        Index("ix_expert_invocation_logs_task_id", "task_id"),
        Index("ix_expert_invocation_logs_stream_mode", "stream_mode"),
    )

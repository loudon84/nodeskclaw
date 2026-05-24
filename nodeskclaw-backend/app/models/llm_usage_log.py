"""LLM Usage Log model -- append-only table for token consumption tracking."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LlmUsageLog(Base):
    """Append-only usage log. Does NOT inherit BaseModel (no updated_at / deleted_at)."""

    __tablename__ = "llm_usage_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    org_llm_key_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("org_llm_keys.id"), nullable=True, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    instance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("instances.id"), nullable=False, index=True
    )
    workspace_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("workspaces.id"), nullable=True, index=True
    )
    attribution_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    org_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    key_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    request_path: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_stream: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    request_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)

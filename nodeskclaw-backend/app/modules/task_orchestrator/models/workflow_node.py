"""Workflow Node Model - Individual node execution state within a workflow."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.modules.task_orchestrator.constants import TABLE_PREFIX


class WorkflowNode(BaseModel):
    """Workflow node execution state.

    Represents the state of a single node within a workflow instance.
    """

    __tablename__ = f"{TABLE_PREFIX}workflow_nodes"

    workflow_instance_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    node_key: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    node_type: Mapped[str] = mapped_column(String(64), nullable=False)
    role_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    executor_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    assigned_agent_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    external_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    timeout_sec: Mapped[int] = mapped_column(Integer, default=1800, nullable=False)
    timeout_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    output_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

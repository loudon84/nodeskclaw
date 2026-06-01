"""Workflow Instance Model - Runtime workflow execution instances."""

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.modules.task_orchestrator.constants import TABLE_PREFIX


class WorkflowInstance(BaseModel):
    """Workflow instance runtime state.

    Represents a single execution of a workflow template.
    """

    __tablename__ = f"{TABLE_PREFIX}workflow_instances"

    template_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    template_key: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    thread_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_ref_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    org_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    workspace_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    trigger_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    input_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    runtime_state: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    current_node_keys: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    source_trace: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_checkpoint_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

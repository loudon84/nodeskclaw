"""Workflow Event Model - Audit trail and timeline events."""

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.modules.task_orchestrator.constants import TABLE_PREFIX


class WorkflowEvent(BaseModel):
    """Workflow event audit trail.

    Records all significant events during workflow execution for timeline and debugging.
    """

    __tablename__ = f"{TABLE_PREFIX}workflow_events"

    workflow_instance_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    workflow_node_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    event_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_by_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_by_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

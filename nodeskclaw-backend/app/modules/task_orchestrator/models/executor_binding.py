"""Executor Binding Model - Executor instance binding and callback tracking."""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.modules.task_orchestrator.constants import TABLE_PREFIX


class ExecutorBinding(BaseModel):
    """Executor binding record.

    Tracks the binding between workflow nodes and external executor instances.
    """

    __tablename__ = f"{TABLE_PREFIX}executor_bindings"

    workflow_instance_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    workflow_node_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    executor_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    assigned_agent_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    external_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    callback_mode: Mapped[str] = mapped_column(String(32), default="poll", nullable=False)
    callback_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

"""Checkpoint Snapshot Model - LangGraph checkpoint persistence."""

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.modules.task_orchestrator.constants import TABLE_PREFIX


class CheckpointSnapshot(BaseModel):
    """LangGraph checkpoint snapshot.

    Stores workflow execution state for interrupt/resume and recovery.
    """

    __tablename__ = f"{TABLE_PREFIX}checkpoints"

    workflow_instance_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    checkpoint_ns: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    checkpoint_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    checkpoint_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    channel_versions: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

"""Human Intervention Model - Human-in-the-loop interaction records."""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.modules.task_orchestrator.constants import TABLE_PREFIX


class HumanIntervention(BaseModel):
    """Human intervention record.

    Tracks human-in-the-loop interactions requiring manual approval or input.
    """

    __tablename__ = f"{TABLE_PREFIX}human_interventions"

    workflow_instance_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    workflow_node_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    intervention_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    requested_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    request_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    response_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

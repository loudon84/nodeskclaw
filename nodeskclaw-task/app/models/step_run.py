from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class StepRun(BaseModel):
    __tablename__ = "step_runs"
    __table_args__ = (
        Index("ix_step_runs_run_id", "run_id"),
    )

    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    step_id: Mapped[str] = mapped_column(String(255), nullable=False)
    step_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    output: Mapped[str] = mapped_column(Text, default="{}", nullable=False)

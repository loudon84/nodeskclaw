from datetime import datetime

from sqlalchemy import DateTime, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


# @lat: [[architecture/skill-agent#RM-17 Public Approval Decision]]
class SkillRunApprovalDecision(BaseModel):
    __tablename__ = "skill_run_approval_decisions"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    approval_id: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    response_body: Mapped[dict] = mapped_column(JSONB, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index(
            "uq_skill_run_approval_decisions_alive",
            "org_id",
            "user_id",
            "run_id",
            "approval_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

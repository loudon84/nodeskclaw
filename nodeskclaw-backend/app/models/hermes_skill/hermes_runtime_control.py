import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class HermesRuntimeControl(BaseModel):
    __tablename__ = "hermes_runtime_controls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    control_key: Mapped[str] = mapped_column(String(128), nullable=False)
    control_value: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        Index(
            "uq_hermes_runtime_controls_org_key",
            "org_id", "control_key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

"""Knowledge audit log ORM model."""

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AuditLog(BaseModel):
    __tablename__ = "knowledge_audit_logs"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    member_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

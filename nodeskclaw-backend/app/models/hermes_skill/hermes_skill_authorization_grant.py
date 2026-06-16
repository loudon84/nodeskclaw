import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class HermesSkillAuthorizationGrant(BaseModel):
    __tablename__ = "hermes_skill_authorization_grants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    skill_id: Mapped[str] = mapped_column(String(255), nullable=False)
    skill_db_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(255), nullable=False)
    workspace_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    can_list: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    can_invoke: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_install: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_manage: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    granted_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        Index(
            "ix_hermes_skill_auth_grant_org_skill",
            "org_id", "skill_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_hermes_skill_auth_grant_subject",
            "org_id", "subject_type", "subject_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

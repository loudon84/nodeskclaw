from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel

SUBJECT_TYPE_USER = "USER"
SUBJECT_TYPE_ORG_ROLE = "ORG_ROLE"
PERMISSION_USE = "USE"
ORG_ROLE_GRANT_SUBJECTS = frozenset({"member", "operator", "admin"})


class IntegrationAccountGrant(BaseModel):
    __tablename__ = "integration_account_grants"
    __table_args__ = (
        Index(
            "uq_integration_account_grants_subject_permission",
            "integration_account_id",
            "subject_type",
            "subject_id",
            "permission",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_integration_account_grants_org_id", "org_id"),
    )

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    integration_account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("integration_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(64), nullable=False)
    permission: Mapped[str] = mapped_column(String(32), nullable=False, default=PERMISSION_USE)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)

"""Member-level MCP Skill authorization grants."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class OrgMemberSkillGrant(BaseModel):
    __tablename__ = "org_member_skill_grants"
    __table_args__ = (
        Index(
            "uq_org_member_skill_grant_active",
            "membership_id",
            "skill_db_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_org_member_skill_grants_org_user",
            "org_id",
            "user_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_org_member_skill_grants_org_skill",
            "org_id",
            "skill_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_org_member_skill_grants_membership",
            "membership_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    membership_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("org_memberships.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    skill_db_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hermes_skills.id", ondelete="CASCADE"),
        nullable=False,
    )
    skill_id: Mapped[str] = mapped_column(String(255), nullable=False)

    can_list: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_invoke: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_manage: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    grant_source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    granted_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)

    organization = relationship("Organization")
    membership = relationship("OrgMembership")
    user = relationship("User", foreign_keys=[user_id])
    skill = relationship("HermesSkill")
    granter = relationship("User", foreign_keys=[granted_by])

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ExpertTeamMember(BaseModel):
    __tablename__ = "expert_team_members"

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("expert_teams.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    expert_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("experts.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    role: Mapped[str | None] = mapped_column(String(128), nullable=True)
    responsibility: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("ix_expert_team_member_team_order", "team_id", "order_no"),
    )

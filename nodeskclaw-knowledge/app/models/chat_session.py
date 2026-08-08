"""Knowledge chat session ORM model."""

from sqlalchemy import Boolean, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ChatSession(BaseModel):
    __tablename__ = "knowledge_chat_sessions"
    __table_args__ = (
        Index(
            "ix_chat_session_member",
            "org_id",
            "member_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    member_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    knowledge_set_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    answer_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="detailed")
    show_citations: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    answer_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")

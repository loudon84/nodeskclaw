"""KnowledgeApplication ACL ORM model."""

from sqlalchemy import Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


# @lat: [[knowledge-objects#Knowledge Application]]
class KnowledgeApplicationAcl(BaseModel):
    __tablename__ = "knowledge_application_acl"
    __table_args__ = (
        Index(
            "uq_application_acl",
            "application_id",
            "subject_type",
            "subject_id",
            "permission",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    application_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(128), nullable=False)
    permission: Mapped[str] = mapped_column(String(32), nullable=False)
    effect: Mapped[str] = mapped_column(String(16), nullable=False, default="allow")
    created_by_member_id: Mapped[str] = mapped_column(String(36), nullable=False)

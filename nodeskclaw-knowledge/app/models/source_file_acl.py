"""SourceFile ACL ORM model."""

from sqlalchemy import Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class SourceFileAcl(BaseModel):
    __tablename__ = "source_file_acl"
    __table_args__ = (
        Index(
            "uq_sf_acl",
            "source_file_id",
            "subject_type",
            "subject_id",
            "permission",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    source_file_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(128), nullable=False)
    permission: Mapped[str] = mapped_column(String(32), nullable=False)
    effect: Mapped[str] = mapped_column(String(16), nullable=False, default="allow")
    created_by_member_id: Mapped[str] = mapped_column(String(36), nullable=False)

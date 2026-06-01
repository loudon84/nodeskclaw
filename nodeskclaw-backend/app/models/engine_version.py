"""Engine version catalog — tracks published runtime versions available for deployment."""

from sqlalchemy import Boolean, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class EngineVersion(BaseModel):
    __tablename__ = "engine_versions"

    __table_args__ = (
        Index(
            "uq_engine_version_runtime_version",
            "runtime", "version",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    runtime: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    image_tag: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="published")
    release_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

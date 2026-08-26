"""BuildProfile ORM model — product build strategy (Standard / Enhanced / Reasoning)."""

from sqlalchemy import Boolean, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


# @lat: [[knowledge-objects#Build Profile]]
class BuildProfile(BaseModel):
    __tablename__ = "knowledge_build_profiles"
    __table_args__ = (
        Index(
            "uq_build_profile_org_name",
            "org_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_build_profile_system_key",
            "system_key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND system_key IS NOT NULL"),
        ),
    )

    org_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    index_types: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    trigger_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    runtime_hints: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

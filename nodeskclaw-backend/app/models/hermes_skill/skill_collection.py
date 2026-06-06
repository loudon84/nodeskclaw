from sqlalchemy import Boolean, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class HermesSkillCollection(BaseModel):
    __tablename__ = "hermes_skill_collections"
    __table_args__ = (
        Index(
            "ix_hermes_skill_coll_name_org_unique",
            "name", "org_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    collection_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    agent_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_read_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    skills: Mapped[list["HermesCollectionSkill"]] = relationship(
        "HermesCollectionSkill",
        back_populates="collection",
        lazy="selectin",
        order_by="HermesCollectionSkill.sort_order",
    )


class HermesCollectionSkill(BaseModel):
    __tablename__ = "hermes_collection_skills"
    __table_args__ = (
        Index(
            "ix_hermes_coll_skill_unique",
            "collection_id", "skill_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    collection_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("hermes_skill_collections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version_constraint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    collection: Mapped["HermesSkillCollection"] = relationship(
        "HermesSkillCollection", back_populates="skills"
    )

"""KnowledgeQualitySnapshot and KnowledgeQualityGatePolicy ORM models."""

# @lat: [[knowledge-objects#Quality Snapshot]]
from datetime import datetime

from sqlalchemy import DateTime, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class KnowledgeQualitySnapshot(BaseModel):
    __tablename__ = "knowledge_quality_snapshots"
    __table_args__ = (
        Index(
            "ix_quality_snapshot_scope",
            "scope_type",
            "scope_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    manifest_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    release_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    subscores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    coverage: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    issues: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    overall_status: Mapped[str] = mapped_column(String(32), nullable=False)
    gate_result: Mapped[str | None] = mapped_column(String(16), nullable=True)
    gate_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class KnowledgeQualityGatePolicy(BaseModel):
    __tablename__ = "knowledge_quality_gate_policies"
    __table_args__ = (
        Index(
            "uq_quality_gate_policy_org",
            "org_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    policy: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by_member_id: Mapped[str] = mapped_column(String(36), nullable=False)

"""ApplicationRetrievalPolicyRevision ORM — Application-level retrieval policy authority."""

# @lat: [[knowledge-objects#Application Retrieval Policy]]
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ApplicationRetrievalPolicyRevision(BaseModel):
    __tablename__ = "application_retrieval_policy_revisions"
    __table_args__ = (
        Index(
            "uq_app_retrieval_policy_revision_version",
            "application_id",
            "revision_number",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_app_retrieval_policy_single_active",
            "application_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND status = 'active'"),
        ),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    query_intelligence_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    provider_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    provider_weights: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    candidate_budget: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fanout_budget: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    latency_budget: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fallback_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    artifact_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fusion_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by_member_id: Mapped[str] = mapped_column(String(36), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

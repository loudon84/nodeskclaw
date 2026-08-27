"""KnowledgeArtifact ORM — derived knowledge catalog."""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class KnowledgeArtifact(BaseModel):
    __tablename__ = "knowledge_artifacts"
    __table_args__ = (
        Index(
            "uq_knowledge_artifact_kb_type_status",
            "org_id",
            "knowledge_base_id",
            "artifact_type",
            "status",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    knowledge_base_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, default="knowledge_base")
    source_file_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    file_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    runtime_binding_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    runtime_resource_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    artifact_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_built")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_manifest_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lineage_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validation_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    coverage_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    provider_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_built_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

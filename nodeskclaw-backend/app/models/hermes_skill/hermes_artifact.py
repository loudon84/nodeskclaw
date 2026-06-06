import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class PermissionScope(str, enum.Enum):
    ORG = "org"
    WORKSPACE = "workspace"
    TASK_CREATOR = "task_creator"
    EXPLICIT = "explicit"


class HermesArtifact(BaseModel):
    __tablename__ = "hermes_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("hermes_tasks.id", ondelete="CASCADE"), nullable=True)
    skill_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    workspace_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    relative_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_type: Mapped[str] = mapped_column(String(32), nullable=False, default="local")
    download_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    permission_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="workspace")
    download_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    preview_supported: Mapped[bool] = mapped_column(default=False)
    source_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_hermes_artifacts_org_task", "org_id", "task_id"),
        Index("ix_hermes_artifacts_org_scope", "org_id", "permission_scope"),
        Index("ix_hermes_artifacts_workspace", "workspace_id"),
        Index("ix_hermes_artifacts_content_type", "content_type"),
    )

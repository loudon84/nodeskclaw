import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Enum, ForeignKey, Index, Integer, String, Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel, Base


class TaskStatus(str, enum.Enum):
    QUEUED = "queued"
    ACCEPTED = "accepted"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class EventType(str, enum.Enum):
    TASK_CREATED = "task.created"
    TASK_QUEUED = "task.queued"
    TASK_ACCEPTED = "task.accepted"
    TASK_STARTED = "task.started"
    TASK_RETRYING = "task.retrying"
    TASK_CANCEL_REQUESTED = "task.cancel_requested"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"
    TASK_TIMEOUT = "task.timeout"
    HERMES_RUN_CREATED = "hermes.run.created"
    HERMES_RUN_STARTED = "hermes.run.started"
    HERMES_RUN_DELTA = "hermes.run.delta"
    HERMES_RUN_COMPLETED = "hermes.run.completed"
    HERMES_RUN_FAILED = "hermes.run.failed"
    ARTIFACT_SCAN_STARTED = "artifact.scan.started"
    ARTIFACT_CREATED = "artifact.created"
    ARTIFACT_SCAN_COMPLETED = "artifact.scan.completed"
    ARTIFACT_SCAN_FAILED = "artifact.scan.failed"
    ARTIFACT_PERMISSION_CHANGED = "artifact.permission_changed"
    ARTIFACT_SHARED = "artifact.shared"
    ARTIFACT_DELETED = "artifact.deleted"


class HermesTask(BaseModel):
    __tablename__ = "hermes_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    task_no: Mapped[str] = mapped_column(String(64), nullable=False)
    skill_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    workspace_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    installation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), nullable=False, default=TaskStatus.QUEUED)
    arguments: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    arguments_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    result_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    hermes_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    artifact_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    dispatch_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dispatch_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_dispatch_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=900)
    run_started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    run_finished_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_hermes_tasks_org_status", "org_id", "status"),
        Index("ix_hermes_tasks_org_skill", "org_id", "skill_id"),
        Index("ix_hermes_tasks_org_agent", "org_id", "agent_id"),
        Index("ix_hermes_tasks_queue_status_created_at", "org_id", "status", "created_at"),
        Index("ix_hermes_tasks_worker_lock", "status", "locked_at"),
        Index(
            "uq_hermes_tasks_task_no_alive", "task_no",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )


class HermesTaskEvent(Base):
    __tablename__ = "hermes_task_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("hermes_tasks.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType), nullable=False)
    event_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_hermes_task_events_task_seq", "task_id", "event_seq"),
        Index("uq_hermes_task_events_task_seq", "task_id", "event_seq", unique=True),
    )

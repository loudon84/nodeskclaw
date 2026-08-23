from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProgressStage(str, Enum):
    preparing = "preparing"
    analyzing = "analyzing"
    retrieving = "retrieving"
    tool_calling = "tool_calling"
    processing = "processing"
    generating = "generating"
    artifact_building = "artifact_building"
    finalizing = "finalizing"


class TaskEventEnvelope(BaseModel):
    event: str
    task_id: str
    timestamp: str | None = None
    event_type: str
    event_seq: int


class TaskStartedEvent(TaskEventEnvelope):
    event: str = "task.started"


class TaskProgressEvent(TaskEventEnvelope):
    event: str = "task.progress"
    stage: str | None = None
    progress: float | None = None
    message: str | None = None


class TaskTimelineEvent(TaskEventEnvelope):
    event: str = "task.timeline"
    data: list[dict[str, Any]] = Field(default_factory=list)


class TaskArtifactReadyPayload(BaseModel):
    artifact_id: str | None = None
    name: str | None = None
    type: str | None = None
    path: str | None = None


class TaskArtifactReadyEvent(TaskEventEnvelope):
    event: str = "task.artifact.ready"
    artifact: TaskArtifactReadyPayload


class TaskCompletedResultPayload(BaseModel):
    summary: str | None = None
    content: str | None = None
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    artifact_mode: str | None = None
    kb_status: str | None = None


class TaskCompletedEvent(TaskEventEnvelope):
    event: str = "task.completed"
    result: TaskCompletedResultPayload = Field(default_factory=TaskCompletedResultPayload)
    artifact_mode: str | None = None
    kb_status: str | None = None


class TaskFailedEvent(TaskEventEnvelope):
    event: str = "task.failed"
    error: Any = None

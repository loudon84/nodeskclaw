from typing import Any

from pydantic import BaseModel, Field


class TaskResultError(BaseModel):
    code: str
    message: str


class TaskResultTaskInfo(BaseModel):
    id: str
    task_no: str
    status: str
    tool_name: str | None = None
    agent_alias: str | None = None
    agent_id: str | None = None
    profile_id: str | None = None
    workspace_id: str | None = None
    created_at: str | None = None
    completed_at: str | None = None


class ArtifactDescriptor(BaseModel):
    id: str
    org_id: str
    task_id: str | None = None
    created_by: str | None = None
    title: str | None = None
    file_name: str
    artifact_type: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    preview_url: str | None = None
    download_url: str | None = None


class TaskSnapshotResultSection(BaseModel):
    ready: bool
    summary: str | None = None
    result_content: str | None = None
    content: str | None = None
    message: str | None = None
    isError: bool | None = None
    error: TaskResultError | None = None


class TaskSnapshotTaskInfo(BaseModel):
    id: str
    task_no: str | None = None
    status: str
    tool_name: str | None = None
    agent_alias: str | None = None
    agent_id: str | None = None
    profile_id: str | None = None
    workspace_id: str | None = None
    routing_metadata: dict[str, Any] | None = None
    created_at: str | None = None
    completed_at: str | None = None


class TaskSnapshotArtifactsSection(BaseModel):
    ready: bool
    items: list[ArtifactDescriptor] = Field(default_factory=list)
    server_artifacts: list[dict[str, Any]] = Field(default_factory=list)


class TaskSnapshotLinks(BaseModel):
    event_stream: str
    result_url: str
    artifact_url: str


class TaskSnapshotResponse(BaseModel):
    task: TaskSnapshotTaskInfo
    status: str
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    result: TaskSnapshotResultSection
    artifacts: TaskSnapshotArtifactsSection
    links: TaskSnapshotLinks
    last_events: list[dict[str, Any]] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None


class TaskResultResponse(BaseModel):
    ready: bool
    status: str
    task_id: str
    task_no: str
    message: str | None = None
    isError: bool | None = None
    error: TaskResultError | None = None
    task: TaskResultTaskInfo | None = None
    primary_artifact: dict[str, Any] | None = None
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    result_summary: str | None = None
    result_content: str | None = None
    content: str | None = None
    artifact_mode: str | None = None
    server_artifacts: list[dict[str, Any]] = Field(default_factory=list)
    artifact_status: str | None = None
    kb_status: str | None = None

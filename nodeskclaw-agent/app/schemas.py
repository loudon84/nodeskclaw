from typing import Any

from pydantic import BaseModel, Field


class CreateRunRequest(BaseModel):
    run_id: str
    dispatch_id: str | None = None
    org_id: str | None = None
    user_id: str | None = None
    tool_name: str
    skill_id: str | None = None
    skill_version: str | None = None
    skill_release_id: str | None = None
    skill_release_digest: str | None = None
    snapshot_hash: str | None = None
    connector_binding_refs: list[str] = Field(default_factory=list)
    knowledge_refs: list[str] = Field(default_factory=list)
    placement: dict[str, Any] = Field(default_factory=dict)
    arguments: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = False
    route_snapshot: dict[str, Any] = Field(default_factory=dict)
    output_policy: dict[str, Any] = Field(default_factory=dict)
    client_context: dict[str, Any] = Field(default_factory=dict)
    request_trace_id: str | None = None
    idempotency_key: str | None = None


class CreateRunResponse(BaseModel):
    run_id: str
    status: str
    snapshot_hash: str
    org_id: str | None = None


class RunView(BaseModel):
    run_id: str
    org_id: str
    user_id: str
    tool_name: str
    status: str
    snapshot: dict[str, Any]
    result: dict[str, Any] | None = None
    attempt_id: str | None = None
    generation: int = 0
    created_at: str
    updated_at: str


class ArtifactDescriptor(BaseModel):
    artifact_id: str
    name: str
    content_type: str | None = None
    size_bytes: int | None = None
    download_url: str | None = None
    checksum_sha256: str | None = None


class RunEventView(BaseModel):
    event_id: str
    run_id: str
    event_type: str
    event_seq: int
    source: str = "agent"
    source_event_id: str | None = None
    timestamp: str
    payload: dict[str, Any] = Field(default_factory=dict)

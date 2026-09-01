from typing import Any

from pydantic import BaseModel, Field

SEMANTIC_EVENT_TYPES = frozenset(
    {
        "assistant.message",
        "reasoning.summary",
        "tool.call",
        "clarify.requested",
        "approval.requested",
        "artifact.persisted",
    }
)

CONTROL_EVENT_PREFIXES_KEEP = ("run.", "step.", "edge.job.")

# Documented known control types (non-exhaustive; KEEP is prefix-based).
CONTROL_EVENT_TYPES_KEEP = frozenset(
    {
        "run.progress",
        "run.completed",
        "run.failed",
        "run.cancelled",
        "run.started",
        "run.plan",
        "run.central_step_completed",
        "run.waiting_edge",
        "run.edge_steps_queued",
        "run.recovered",
        "run.artifact_ready",
        "run.created",
        "run.queued",
        "run.resuming",
        "run.cancelling",
        "step.init",
        "step.completed",
        "step.failed",
        "step.cancelled",
        "step.running",
        "edge.job.completed",
        "edge.job.failed",
        "edge.job.cancelled",
    }
)

TOOL_CALL_STATUSES = frozenset({"started", "completed", "failed"})

_SEMANTIC_PAYLOAD_FIELDS = {
    "assistant.message": frozenset({"text"}),
    "reasoning.summary": frozenset({"summary"}),
    "tool.call": frozenset({"tool_name", "call_id", "status"}),
    "clarify.requested": frozenset({"question", "options"}),
    "approval.requested": frozenset({"approval_id", "summary"}),
    "artifact.persisted": frozenset({"artifact_id", "name", "content_type", "size", "checksum_sha256"}),
}

_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "storage_key",
        "storage_ref",
        "gateway_url",
        "gateway_token",
        "token",
        "authorization",
        "arguments",
        "raw_arguments",
        "presigned_url",
        "bytes",
        "content_base64",
        "chain_of_thought",
        "reasoning",
    }
)


def is_semantic_event_type(event_type: str) -> bool:
    return event_type in SEMANTIC_EVENT_TYPES


def is_control_event_type(event_type: str) -> bool:
    if not event_type or is_semantic_event_type(event_type):
        return False
    return event_type.startswith(CONTROL_EVENT_PREFIXES_KEEP)

def validate_semantic_event_payload(event_type: str, payload: dict[str, Any] | None) -> str | None:
    """Return stable rejection reason, or None when the semantic payload is valid."""
    data = payload or {}
    if not isinstance(data, dict):
        return "invalid_semantic_payload"
    if _FORBIDDEN_PAYLOAD_KEYS.intersection(data.keys()):
        return "forbidden_semantic_payload_field"
    allowed_fields = _SEMANTIC_PAYLOAD_FIELDS.get(event_type)
    if allowed_fields is not None and set(data).difference(allowed_fields):
        return "unexpected_semantic_payload_field"

    if event_type == "assistant.message":
        text = data.get("text")
        if not isinstance(text, str) or not text:
            return "missing_assistant_text"
        return None

    if event_type == "reasoning.summary":
        summary = data.get("summary")
        if not isinstance(summary, str) or not summary:
            return "missing_reasoning_summary"
        return None

    if event_type == "tool.call":
        tool_name = data.get("tool_name")
        call_id = data.get("call_id")
        status = data.get("status")
        if not isinstance(tool_name, str) or not tool_name:
            return "missing_tool_name"
        if not isinstance(call_id, str) or not call_id:
            return "missing_call_id"
        if status not in TOOL_CALL_STATUSES:
            return "invalid_tool_call_status"
        return None

    if event_type == "clarify.requested":
        question = data.get("question")
        if not isinstance(question, str) or not question:
            return "missing_clarify_question"
        options = data.get("options")
        if options is not None and not isinstance(options, list):
            return "invalid_clarify_options"
        return None

    if event_type == "approval.requested":
        approval_id = data.get("approval_id")
        summary = data.get("summary")
        if not isinstance(approval_id, str) or not approval_id:
            return "missing_approval_id"
        if not isinstance(summary, str) or not summary:
            return "missing_approval_summary"
        return None

    if event_type == "artifact.persisted":
        artifact_id = data.get("artifact_id")
        name = data.get("name")
        size = data.get("size")
        checksum = data.get("checksum_sha256")
        if not isinstance(artifact_id, str) or not artifact_id:
            return "missing_artifact_id"
        if not isinstance(name, str) or not name:
            return "missing_artifact_name"
        if not isinstance(size, int) or size < 0:
            return "invalid_artifact_size"
        if not isinstance(checksum, str) or not checksum:
            return "missing_artifact_checksum"
        content_type = data.get("content_type")
        if content_type is not None and not isinstance(content_type, str):
            return "invalid_artifact_content_type"
        return None

    return "unknown_semantic_type"


class CreateRunRequest(BaseModel):
    run_id: str | None = None
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
    run_session_id: str | None = None
    execution_context: dict[str, Any] | None = None
    context_version: int | None = None


class CreateRunResponse(BaseModel):
    run_id: str
    status: str
    snapshot_hash: str
    org_id: str | None = None
    run_session_id: str | None = None


class RunView(BaseModel):
    run_id: str
    org_id: str
    user_id: str
    tool_name: str
    status: str
    snapshot: dict[str, Any]
    result: dict[str, Any] | None = None
    attempt_id: str | None = None
    run_session_id: str | None = None
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
    storage_state: str = "persisted"


class RunEventView(BaseModel):
    event_id: str
    run_id: str
    event_type: str
    event_seq: int
    source: str = "agent"
    source_event_id: str | None = None
    request_trace_id: str | None = None
    timestamp: str
    payload: dict[str, Any] = Field(default_factory=dict)


class EventsResponse(BaseModel):
    org_id: str
    run_id: str
    items: list[RunEventView] = Field(default_factory=list)
    next_seq: int | None = None


class ResultResponse(BaseModel):
    org_id: str
    run_id: str
    status: str
    result: dict[str, Any] | None = None


class ArtifactsResponse(BaseModel):
    org_id: str
    run_id: str
    items: list[ArtifactDescriptor] = Field(default_factory=list)


class MutationResponse(BaseModel):
    org_id: str
    run_id: str
    status: str
    idempotent: bool = True


class IngestEventItem(BaseModel):
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    event_seq: int | None = None
    step_id: str | None = None
    attempt_id: str | None = None
    delivery_generation: int | None = None
    source: str = "edge"
    source_event_id: str | None = None


class IngestEventsRequest(BaseModel):
    events: list[IngestEventItem] = Field(default_factory=list)


class IngestEventsResponse(BaseModel):
    accepted_count: int
    rejected_count: int = 0
    run_id: str
    status: str


class RunStepView(BaseModel):
    step_id: str
    owner_role: str
    engine: str
    status: str
    depends_on: list[str] = Field(default_factory=list)
    required: bool = True
    required_artifacts: list[str] = Field(default_factory=list)
    attempt_id: str | None = None
    run_generation: int = 0
    edge_job_id: str | None = None
    version: int = 1
    result: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class StepPlanResponse(BaseModel):
    run_id: str
    org_id: str
    steps: list[RunStepView] = Field(default_factory=list)


class EventRejectionView(BaseModel):
    id: str
    run_id: str
    event_id: str | None = None
    source_event_id: str | None = None
    reason: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ArtifactUploadRequest(BaseModel):
    name: str
    content_base64: str
    content_type: str | None = "text/plain"
    checksum_sha256: str | None = None
    attempt_id: str | None = None
    step_id: str | None = None
    generation: int | None = None
    size: int | None = None
    upload_mode: str | None = "eager"
    idempotency_key: str | None = None




import json
from typing import Any

from pydantic import BaseModel, Field

SEMANTIC_EVENT_TYPES = frozenset(
    {
        "assistant.delta",
        "assistant.message",
        "reasoning.summary",
        "tool.call",
        "tool.result",
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
TOOL_RESULT_STATUSES = frozenset({"completed", "failed"})

MAX_ASSISTANT_DELTA_UTF8_BYTES = 64 * 1024
MAX_ASSISTANT_SNAPSHOT_UTF8_BYTES = 1 * 1024 * 1024
MAX_TOOL_EVENT_UTF8_BYTES = 64 * 1024
MAX_TOOL_EVENT_JSON_DEPTH = 8

_SEMANTIC_PAYLOAD_FIELDS = {
    "assistant.delta": frozenset({"message_id", "delta_seq", "delta"}),
    "assistant.message": frozenset({"message_id", "text"}),
    "reasoning.summary": frozenset({"summary"}),
    "tool.call": frozenset({"tool_name", "call_id", "status", "arguments", "redacted", "truncated"}),
    "tool.result": frozenset(
        {
            "tool_name",
            "call_id",
            "status",
            "content",
            "structured_content",
            "artifact_ids",
            "error_code",
            "error_message",
            "redacted",
            "truncated",
        }
    ),
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
        "raw_arguments",
        "presigned_url",
        "bytes",
        "content_base64",
        "chain_of_thought",
        "reasoning",
    }
)


def _json_depth(value: Any, depth: int = 1) -> int:
    if isinstance(value, dict):
        if not value:
            return depth
        return max(_json_depth(item, depth + 1) for item in value.values())
    if isinstance(value, list):
        if not value:
            return depth
        return max(_json_depth(item, depth + 1) for item in value)
    return depth


def _tool_event_bounds_reason(data: dict[str, Any]) -> str | None:
    if _json_depth(data) > MAX_TOOL_EVENT_JSON_DEPTH:
        return "tool_event_too_deep"
    try:
        encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError):
        return "invalid_semantic_payload"
    if len(encoded) > MAX_TOOL_EVENT_UTF8_BYTES:
        return "tool_event_too_large"
    return None


def _optional_bool_reason(data: dict[str, Any], field: str, reason: str) -> str | None:
    if field not in data:
        return None
    if not isinstance(data.get(field), bool):
        return reason
    return None


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

    if event_type == "assistant.delta":
        message_id = data.get("message_id")
        delta_seq = data.get("delta_seq")
        delta = data.get("delta")
        if not isinstance(message_id, str) or not message_id:
            return "missing_assistant_message_id"
        if not isinstance(delta_seq, int) or isinstance(delta_seq, bool) or delta_seq < 1:
            return "invalid_assistant_delta_seq"
        if not isinstance(delta, str) or not delta:
            return "missing_assistant_delta"
        if len(delta.encode("utf-8")) > MAX_ASSISTANT_DELTA_UTF8_BYTES:
            return "assistant_delta_too_large"
        return None

    if event_type == "assistant.message":
        message_id = data.get("message_id")
        text = data.get("text")
        if not isinstance(message_id, str) or not message_id:
            return "missing_assistant_message_id"
        if not isinstance(text, str) or not text:
            return "missing_assistant_text"
        if len(text.encode("utf-8")) > MAX_ASSISTANT_SNAPSHOT_UTF8_BYTES:
            return "assistant_snapshot_too_large"
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
        if "arguments" in data and data.get("arguments") is not None and not isinstance(data.get("arguments"), dict):
            return "invalid_tool_arguments"
        redacted_reason = _optional_bool_reason(data, "redacted", "invalid_tool_redacted")
        if redacted_reason:
            return redacted_reason
        truncated_reason = _optional_bool_reason(data, "truncated", "invalid_tool_truncated")
        if truncated_reason:
            return truncated_reason
        return _tool_event_bounds_reason(data)

    if event_type == "tool.result":
        tool_name = data.get("tool_name")
        call_id = data.get("call_id")
        status = data.get("status")
        if not isinstance(tool_name, str) or not tool_name:
            return "missing_tool_name"
        if not isinstance(call_id, str) or not call_id:
            return "missing_call_id"
        if status not in TOOL_RESULT_STATUSES:
            return "invalid_tool_result_status"
        if "content" in data and data.get("content") is not None and not isinstance(data.get("content"), str):
            return "invalid_tool_result_content"
        if "artifact_ids" in data and data.get("artifact_ids") is not None:
            artifact_ids = data.get("artifact_ids")
            if not isinstance(artifact_ids, list) or any(not isinstance(item, str) or not item for item in artifact_ids):
                return "invalid_tool_result_artifact_ids"
        if "error_code" in data and data.get("error_code") is not None and not isinstance(data.get("error_code"), str):
            return "invalid_tool_result_error_code"
        if "error_message" in data and data.get("error_message") is not None and not isinstance(data.get("error_message"), str):
            return "invalid_tool_result_error_message"
        if status == "failed":
            error_code = data.get("error_code")
            if not isinstance(error_code, str) or not error_code:
                return "missing_tool_result_error_code"
        redacted_reason = _optional_bool_reason(data, "redacted", "invalid_tool_redacted")
        if redacted_reason:
            return redacted_reason
        truncated_reason = _optional_bool_reason(data, "truncated", "invalid_tool_truncated")
        if truncated_reason:
            return truncated_reason
        return _tool_event_bounds_reason(data)

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
    delegation_topology: str | None = None
    runtime_capability_ref: dict[str, Any] | None = None


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




import json
from typing import Any

from app.core.config import settings
from app.models.hermes_skill.hermes_task import EventType, HermesTaskEvent, TaskStatus


_TERMINAL_STATUSES = frozenset({
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
    TaskStatus.TIMEOUT,
})

_SSE_EVENT_NAMES: dict[EventType, str] = {
    EventType.TASK_STARTED: "task.started",
    EventType.TASK_QUEUED: "task.started",
    EventType.TASK_ACCEPTED: "task.started",
    EventType.HERMES_RUN_STARTED: "task.started",
    EventType.HERMES_RUN_DELTA: "task.progress",
    EventType.ARTIFACT_CREATED: "task.artifact.ready",
    EventType.TASK_COMPLETED: "task.completed",
    EventType.HERMES_RUN_COMPLETED: "task.completed",
    EventType.TASK_FAILED: "task.failed",
    EventType.TASK_TIMEOUT: "task.failed",
    EventType.TASK_CANCELLED: "task.failed",
    EventType.HERMES_RUN_FAILED: "task.failed",
}


def unwrap_event_payload(payload: dict | None) -> dict:
    if not payload:
        return {}
    if payload.get("source") == "hermes" and isinstance(payload.get("payload"), dict):
        inner = dict(payload["payload"])
        if payload.get("hermes_event_seq") is not None:
            inner["hermes_event_seq"] = payload["hermes_event_seq"]
        return inner
    return payload


def resolve_sse_event_name(event: HermesTaskEvent) -> str:
    payload = unwrap_event_payload(event.payload)
    mcp_event = payload.get("mcp_event")
    if isinstance(mcp_event, str) and mcp_event:
        return mcp_event
    return _SSE_EVENT_NAMES.get(event.event_type, event.event_type.value)


def build_sse_data(
    event: HermesTaskEvent,
    task_id: str,
    *,
    enriched_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = unwrap_event_payload(event.payload)
    sse_name = resolve_sse_event_name(event)
    data: dict[str, Any] = {
        "event": sse_name,
        "task_id": task_id,
        "timestamp": event.created_at.isoformat() if event.created_at else None,
        "event_type": event.event_type.value,
        "event_seq": event.event_seq,
    }

    if sse_name == "task.progress":
        data["stage"] = payload.get("stage") or payload.get("tool_name") or payload.get("step")
        if payload.get("progress") is not None:
            data["progress"] = payload.get("progress")
        if payload.get("message"):
            data["message"] = payload.get("message")
    elif sse_name == "task.artifact.ready":
        artifact = payload.get("artifact") or payload
        data["artifact"] = {
            "artifact_id": artifact.get("artifact_id") or artifact.get("id"),
            "name": artifact.get("name") or artifact.get("file_name"),
            "type": artifact.get("type") or artifact.get("artifact_type") or "report",
            "path": artifact.get("path") or artifact.get("suggested_workspace_path"),
        }
    elif sse_name == "task.completed":
        result = payload.get("result") or {}
        if enriched_result:
            result = {
                "summary": enriched_result.get("result_summary"),
                "artifacts": enriched_result.get("server_artifacts") or [],
                "artifact_mode": enriched_result.get("artifact_mode"),
                "kb_status": enriched_result.get("kb_status"),
            }
        data["result"] = result
    elif sse_name == "task.failed":
        data["error"] = (
            payload.get("error")
            or payload.get("error_message")
            or payload.get("message")
            or event.event_type.value
        )
    elif sse_name == "task.timeline":
        data["data"] = payload.get("data") or payload.get("timeline") or []
    else:
        if payload:
            data["payload"] = payload

    return data


def format_sse_message(
    event: HermesTaskEvent,
    task_id: str,
    *,
    enriched_result: dict[str, Any] | None = None,
) -> str:
    sse_name = resolve_sse_event_name(event)
    data = build_sse_data(event, task_id, enriched_result=enriched_result)
    body = json.dumps(data, ensure_ascii=False)
    return f"id: {task_id}-{event.event_seq}\nevent: {sse_name}\ndata: {body}\n\n"


def build_timeline_snapshot(events: list[HermesTaskEvent]) -> dict[str, Any] | None:
    stages: list[dict[str, str]] = []
    seen: set[str] = set()
    for event in events:
        payload = unwrap_event_payload(event.payload)
        stage = payload.get("stage") or payload.get("tool_name") or payload.get("step")
        if not stage or stage in seen:
            continue
        seen.add(str(stage))
        if event.event_type in (EventType.TASK_COMPLETED, EventType.HERMES_RUN_COMPLETED):
            status = "done"
        elif event.event_type in (EventType.TASK_FAILED, EventType.TASK_TIMEOUT, EventType.TASK_CANCELLED):
            status = "failed"
        else:
            status = "running"
        stages.append({"stage": str(stage), "status": status})
    if not stages:
        return None
    return {"event": "task.timeline", "data": stages}


def is_terminal_task_status(status: TaskStatus | None) -> bool:
    return status in _TERMINAL_STATUSES if status else False


def should_enrich_completed(event: HermesTaskEvent) -> bool:
    if not settings.MCP_TASK_SSE_INCLUDE_RESULT_ON_COMPLETE:
        return False
    sse_name = resolve_sse_event_name(event)
    if sse_name != "task.completed":
        return False
    payload = unwrap_event_payload(event.payload)
    result = payload.get("result")
    return not (isinstance(result, dict) and result.get("summary"))

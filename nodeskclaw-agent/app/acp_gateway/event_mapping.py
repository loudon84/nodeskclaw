from __future__ import annotations

from typing import Any

from app.acp_gateway.resources import artifact_resource_link, public_artifact_uri

DROPPED_EVENTS = frozenset(
    {
        "run.progress",
        "run.queued",
        "run.created",
        "run.cancelling",
        "run.resuming",
        "run.started",
        "run.plan",
    }
)

TERMINAL_EVENTS = frozenset({"run.completed", "run.cancelled", "run.failed", "run.timed_out"})


def strip_runtime_secrets(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        if key in {"runtime_run_id", "gateway_url", "gateway_token", "token", "authorization"}:
            continue
        if isinstance(value, dict):
            cleaned[key] = strip_runtime_secrets(value)
        else:
            cleaned[key] = value
    return cleaned


def map_event(
    event: Any,
    *,
    agent_ref: str,
) -> tuple[list[dict[str, Any]], str | None, dict[str, Any] | None]:
    event_type = event.get("event_type") if isinstance(event, dict) else getattr(event, "event_type", None)
    raw_payload = event.get("payload") if isinstance(event, dict) else getattr(event, "payload", None)
    payload = strip_runtime_secrets(dict(raw_payload or {}))
    run_id = event.get("run_id") if isinstance(event, dict) else getattr(event, "run_id", None)
    seq = event.get("event_seq") if isinstance(event, dict) else getattr(event, "event_seq", None)
    updates: list[dict[str, Any]] = []
    stop_reason: str | None = None
    permission: dict[str, Any] | None = None

    if event_type in DROPPED_EVENTS:
        return updates, None, None
    if event_type == "assistant.delta":
        updates.append(
            {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": "text", "text": payload.get("delta") or ""},
                "seq": seq,
            }
        )
    elif event_type == "assistant.message":
        updates.append(
            {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": "text", "text": payload.get("text") or ""},
                "seq": seq,
            }
        )
    elif event_type == "reasoning.summary":
        updates.append(
            {
                "sessionUpdate": "agent_thought_chunk",
                "content": {"type": "text", "text": payload.get("summary") or ""},
                "seq": seq,
            }
        )
    elif event_type == "tool.call":
        updates.append(
            {
                "sessionUpdate": "tool_call",
                "toolCallId": payload.get("call_id"),
                "title": payload.get("tool_name"),
                "status": payload.get("status") or "pending",
                "seq": seq,
            }
        )
    elif event_type == "tool.result":
        updates.append(
            {
                "sessionUpdate": "tool_call_update",
                "toolCallId": payload.get("call_id"),
                "status": payload.get("status") or "completed",
                "seq": seq,
            }
        )
    elif event_type in {"approval.requested", "connector.approval.requested"}:
        permission = {
            "event_type": event_type,
            "approval_id": payload.get("approval_id"),
            "summary": payload.get("summary") or payload.get("title") or "approval required",
            "seq": seq,
        }
    elif event_type == "clarify.requested":
        updates.append(
            {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": "text", "text": payload.get("question") or ""},
                "seq": seq,
            }
        )
        stop_reason = "end_turn"
    elif event_type == "artifact.persisted":
        artifact_id = str(payload.get("artifact_id") or "")
        updates.append(
            {
                "sessionUpdate": "agent_message_chunk",
                "content": {
                    "type": "resource_link",
                    "uri": public_artifact_uri(run_id=str(run_id), artifact_id=artifact_id),
                    "name": payload.get("name") or artifact_id,
                    "downloadPath": artifact_resource_link(
                        agent_ref=agent_ref,
                        run_id=str(run_id),
                        artifact_id=artifact_id,
                    ),
                },
                "seq": seq,
            }
        )
    elif event_type == "run.completed":
        stop_reason = "end_turn"
    elif event_type == "run.cancelled":
        stop_reason = "cancelled"
    elif event_type in {"run.failed", "run.timed_out"}:
        stop_reason = "ACP_REMOTE_RUN_FAILED"
    return updates, stop_reason, permission

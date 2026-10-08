from __future__ import annotations

from typing import Any

from app.acp_gateway.assistant_reconciler import AssistantReconciler
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

_SECRET_KEYS = frozenset(
    {
        "runtime_run_id",
        "runtime_session_id",
        "gateway_url",
        "gateway_token",
        "token",
        "authorization",
        "child_session_id",
    }
)


def strip_runtime_secrets(payload: Any) -> Any:
    if isinstance(payload, dict):
        cleaned: dict[str, Any] = {}
        for key, value in payload.items():
            if key in _SECRET_KEYS:
                continue
            cleaned[key] = strip_runtime_secrets(value)
        return cleaned
    if isinstance(payload, list):
        return [strip_runtime_secrets(item) for item in payload]
    return payload


def _tool_call_status(raw: str | None) -> str:
    status = str(raw or "").strip()
    if status == "started":
        return "in_progress"
    if status in {"in_progress", "completed", "failed"}:
        return status
    if status == "pending":
        return "in_progress"
    return "in_progress"


def map_event(
    event: Any,
    *,
    agent_ref: str,
    reconciler: AssistantReconciler | None = None,
    silent: bool = False,
) -> tuple[list[dict[str, Any]], str | None, dict[str, Any] | None]:
    event_type = event.get("event_type") if isinstance(event, dict) else getattr(event, "event_type", None)
    raw_payload = event.get("payload") if isinstance(event, dict) else getattr(event, "payload", None)
    payload = strip_runtime_secrets(dict(raw_payload or {}))
    run_id = event.get("run_id") if isinstance(event, dict) else getattr(event, "run_id", None)
    seq = event.get("event_seq") if isinstance(event, dict) else getattr(event, "event_seq", None)
    updates: list[dict[str, Any]] = []
    stop_reason: str | None = None
    permission: dict[str, Any] | None = None
    recon = reconciler or AssistantReconciler()

    if event_type in DROPPED_EVENTS:
        return updates, None, None
    if event_type == "assistant.delta":
        message_id = str(payload.get("message_id") or "")
        delta = payload.get("delta") or ""
        if silent:
            recon.silent_apply_delta(message_id, delta)
            return updates, None, None
        text = recon.apply_delta(message_id, delta)
        if text:
            updates.append(
                {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": text},
                    "seq": seq,
                }
            )
    elif event_type == "assistant.message":
        message_id = str(payload.get("message_id") or "")
        snapshot = payload.get("text") or ""
        if silent:
            recon.silent_apply_snapshot(message_id, snapshot)
            return updates, None, None
        suffix = recon.apply_snapshot(message_id, snapshot)
        if suffix:
            updates.append(
                {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": suffix},
                    "seq": seq,
                }
            )
    elif event_type == "reasoning.summary":
        if not silent:
            updates.append(
                {
                    "sessionUpdate": "agent_thought_chunk",
                    "content": {"type": "text", "text": payload.get("summary") or ""},
                    "seq": seq,
                }
            )
    elif event_type == "tool.call":
        if not silent:
            update: dict[str, Any] = {
                "sessionUpdate": "tool_call",
                "toolCallId": payload.get("call_id"),
                "title": payload.get("tool_name"),
                "status": _tool_call_status(payload.get("status")),
                "seq": seq,
            }
            if "arguments" in payload and payload.get("arguments") is not None:
                update["rawInput"] = payload.get("arguments")
            if "redacted" in payload:
                update["redacted"] = bool(payload.get("redacted"))
            if "truncated" in payload:
                update["truncated"] = bool(payload.get("truncated"))
            updates.append(update)
    elif event_type == "tool.result":
        if not silent:
            update = {
                "sessionUpdate": "tool_call_update",
                "toolCallId": payload.get("call_id"),
                "status": payload.get("status") or "completed",
                "seq": seq,
            }
            if "content" in payload and payload.get("content") is not None:
                update["content"] = payload.get("content")
            if "structured_content" in payload and payload.get("structured_content") is not None:
                update["structuredContent"] = payload.get("structured_content")
            if "error_code" in payload and payload.get("error_code") is not None:
                update["errorCode"] = payload.get("error_code")
            if "error_message" in payload and payload.get("error_message") is not None:
                update["errorMessage"] = payload.get("error_message")
            if "redacted" in payload:
                update["redacted"] = bool(payload.get("redacted"))
            if "truncated" in payload:
                update["truncated"] = bool(payload.get("truncated"))
            updates.append(update)
    elif event_type in {"approval.requested", "connector.approval.requested"}:
        if not silent:
            permission = {
                "event_type": event_type,
                "approval_id": payload.get("approval_id"),
                "summary": payload.get("summary") or payload.get("title") or "approval required",
                "seq": seq,
            }
    elif event_type == "clarify.requested":
        if not silent:
            updates.append(
                {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": payload.get("question") or ""},
                    "seq": seq,
                }
            )
        stop_reason = "end_turn"
    elif event_type == "artifact.persisted":
        if not silent:
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
        error_code = str(payload.get("error_code") or "")
        if error_code == "ACP_RUNTIME_SESSION_BINDING_MISSING":
            stop_reason = "ACP_RUNTIME_SESSION_BINDING_MISSING"
        elif (
            error_code == "RUNTIME_CAPABILITY_MISSING"
            and payload.get("capability") == "run_tool_event_details_v1"
        ):
            stop_reason = "ACP_RUNTIME_UNAVAILABLE"
        else:
            stop_reason = "ACP_REMOTE_RUN_FAILED"
    return updates, stop_reason, permission

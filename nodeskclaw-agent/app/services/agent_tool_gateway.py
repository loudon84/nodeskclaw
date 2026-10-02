from __future__ import annotations

import hashlib
import json
from typing import Any

import httpx

MCP_CAPABILITY_NAMES = ("mcp_servers", "mcp_tool_surface")
APPROVAL_EVENT = "connector.approval.requested"
RESULT_EVENT = "connector.tool.result"


def arguments_digest(arguments: dict[str, Any] | None) -> str:
    body = arguments if isinstance(arguments, dict) else {}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def hermes_mcp_feature(capabilities: dict[str, Any] | None) -> str | None:
    payload = capabilities or {}
    features = payload.get("features") or payload.get("capabilities") or []
    present: set[str] = set()
    if isinstance(features, dict):
        present = {str(key) for key, value in features.items() if value}
    elif isinstance(features, list):
        present = {str(item) for item in features if item}
    for name in MCP_CAPABILITY_NAMES:
        if name in present:
            return name
    return None


def find_tool_result(events: list[dict[str, Any]], *, tool_call_id: str, digest: str) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.get("event_type") != RESULT_EVENT:
            continue
        payload = event.get("payload") or {}
        if payload.get("tool_call_id") == tool_call_id and payload.get("arguments_digest") == digest:
            return payload
    return None


def find_argument_conflict(events: list[dict[str, Any]], *, tool_call_id: str, digest: str) -> bool:
    for event in events:
        payload = event.get("payload") or {}
        if str(payload.get("tool_call_id") or "") != tool_call_id:
            continue
        prior = str(payload.get("arguments_digest") or "")
        if prior and prior != digest:
            return True
    return False


def find_pending_approval(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    decided = {
        str((event.get("payload") or {}).get("approval_id"))
        for event in events
        if event.get("event_type") == RESULT_EVENT
    }
    for event in reversed(events):
        if event.get("event_type") != APPROVAL_EVENT:
            continue
        payload = event.get("payload") or {}
        approval_id = str(payload.get("approval_id") or "")
        if approval_id and approval_id not in decided:
            return payload
    return None


def decide_tool_call(
    *,
    generation_matches: bool,
    tool_listed: bool,
    run_waiting: bool,
    pending_other: bool,
    stored_result: dict[str, Any] | None,
) -> str:
    if not generation_matches:
        return "fail_run"
    if stored_result is not None:
        return "replay"
    if not tool_listed:
        return "deny_unknown"
    if run_waiting or pending_other:
        return "tool_error"
    return "wait_approval"


def classify_connector_exception(exc: BaseException) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return "tool_error"
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, OSError)):
        return "outcome_unknown"
    return "fail_run"


def public_tool_view(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": tool.get("tool_name"),
        "description": tool.get("description") or "",
        "inputSchema": tool.get("input_schema") or {"type": "object"},
    }

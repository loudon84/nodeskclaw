#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ENVELOPE_IGNORE_KEYS = frozenset(
    {
        "run_id",
        "created_at",
        "updated_at",
        "request_trace_id",
        "timestamp",
        "committed",
        "tool_name",
    }
)

FORBIDDEN_KEYS = frozenset(
    {
        "task_id",
        "task_no",
        "agent_alias",
        "agent_id",
        "profile_id",
        "workspace_id",
        "installation_id",
        "routing_reason",
        "event_token_url",
        "wait_strategy",
        "gateway_token",
        "env_file",
        "runtime_run_id",
        "runtime_session_id",
    }
)

FORBIDDEN_SUBSTRINGS = (
    "/api/v1/hermes/tasks/",
    "token=",
    "API_SERVER_KEY",
)

TERMINAL_EVENTS = {
    "COMPLETED": "run.completed",
    "FAILED": "run.failed",
    "CANCELLED": "run.cancelled",
    "TIMED_OUT": "run.timed_out",
}

REDACT_KEY_MARKERS = (
    "token",
    "secret",
    "password",
    "api_key",
    "authorization",
    "cookie",
    "gateway_token",
    "env_file",
    "jwt",
)


class LiveBlocked(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise LiveBlocked("RM12_LIVE_EVIDENCE_BLOCKED", f"missing environment variable: {name}")
    return value


def timeout_seconds() -> int:
    raw = os.getenv("RM12_TIMEOUT_SECONDS", "60").strip() or "60"
    try:
        value = int(raw)
    except ValueError as exc:
        raise LiveBlocked("RM12_LIVE_CONFORMANCE_BLOCKED", "RM12_TIMEOUT_SECONDS must be int") from exc
    if value <= 0:
        raise LiveBlocked("RM12_LIVE_CONFORMANCE_BLOCKED", "RM12_TIMEOUT_SECONDS must be > 0")
    return value


def redact(value: Any, extra_secrets: tuple[str, ...] = ()) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, nested in value.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in REDACT_KEY_MARKERS):
                out[key] = "[REDACTED]"
            else:
                out[key] = redact(nested, extra_secrets)
        return out
    if isinstance(value, list):
        return [redact(item, extra_secrets) for item in value]
    if isinstance(value, str):
        text = value
        for secret in extra_secrets:
            if secret and secret in text:
                text = text.replace(secret, "[REDACTED]")
        return text
    return value


def scan_public_surface(value: Any, trail: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in FORBIDDEN_KEYS:
                errors.append(f"{trail}.{key}")
            errors.extend(scan_public_surface(nested, f"{trail}.{key}"))
        return errors
    if isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(scan_public_surface(item, f"{trail}[{index}]"))
        return errors
    if isinstance(value, str):
        for fragment in FORBIDDEN_SUBSTRINGS:
            if fragment in value:
                errors.append(f"{trail} contains {fragment}")
    return errors


def _http(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    body: dict[str, Any] | None = None,
    timeout: int,
    accept: str | None = None,
) -> tuple[int, dict[str, str], bytes]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req_headers = dict(headers)
    if body is not None:
        req_headers["Content-Type"] = "application/json"
    if accept:
        req_headers["Accept"] = accept
    request = Request(url, data=data, headers=req_headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            return int(response.status), {k.lower(): v for k, v in response.headers.items()}, response.read()
    except HTTPError as exc:
        payload = exc.read() if exc.fp else b""
        return int(exc.code), {k.lower(): v for k, v in (exc.headers.items() if exc.headers else [])}, payload
    except URLError as exc:
        raise LiveBlocked("RM12_LIVE_CONFORMANCE_BLOCKED", f"unreachable {url}: {exc.reason}") from exc


def _json_body(raw: bytes) -> Any:
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def unwrap_data(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload and isinstance(payload["data"], (dict, list)):
        return payload["data"]
    return payload


def mcp_call(
    base: str,
    token: str,
    org_id: str,
    method: str,
    params: dict[str, Any],
    *,
    timeout: int,
    idempotency_key: str | None = None,
) -> tuple[int, dict[str, Any]]:
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Org-Id": org_id,
    }
    if idempotency_key:
        headers["X-Idempotency-Key"] = idempotency_key
    status, _, raw = _http(
        "POST",
        f"{base.rstrip('/')}/api/v1/mcp",
        headers=headers,
        body={"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": method, "params": params},
        timeout=timeout,
    )
    parsed = _json_body(raw)
    if not isinstance(parsed, dict):
        raise LiveBlocked("RM12_LIVE_CONFORMANCE_BLOCKED", f"MCP {method} returned non-JSON")
    return status, parsed


def public_get(base: str, token: str, org_id: str, path: str, timeout: int) -> tuple[int, Any]:
    status, _, raw = _http(
        "GET",
        f"{base.rstrip('/')}{path}",
        headers={"Authorization": f"Bearer {token}", "X-Org-Id": org_id},
        timeout=timeout,
    )
    return status, unwrap_data(_json_body(raw))


def public_cancel(base: str, token: str, org_id: str, run_id: str, timeout: int) -> int:
    status, _, _ = _http(
        "POST",
        f"{base.rstrip('/')}/api/v1/runs/{run_id}/cancel",
        headers={"Authorization": f"Bearer {token}", "X-Org-Id": org_id},
        body={},
        timeout=timeout,
    )
    return status


def agent_ingest(
    agent_base: str,
    token: str,
    org_id: str,
    run_id: str,
    event_type: str,
    timeout: int,
) -> int:
    status, _, raw = _http(
        "POST",
        f"{agent_base.rstrip('/')}/internal/v1/runs/{run_id}/events/ingest",
        headers={
            "X-Skill-Agent-Token": token,
            "X-Exec-Org-Id": org_id,
        },
        body={
            "org_id": org_id,
            "events": [
                {
                    "event_type": event_type,
                    "payload": {"phase": event_type.rsplit(".", 1)[-1].upper(), "source": "rm12-live"},
                    "source": "agent",
                    "source_event_id": f"rm12-live:{run_id}:{event_type}",
                }
            ],
        },
        timeout=timeout,
    )
    if status >= 400:
        detail = raw.decode("utf-8", errors="replace")[:300]
        raise LiveBlocked("RM12_LIVE_CONFORMANCE_BLOCKED", f"ingest {event_type} HTTP {status}: {detail}")
    return status


def read_sse(
    base: str,
    token: str,
    org_id: str,
    run_id: str,
    timeout: int,
) -> tuple[list[dict[str, Any]], bool]:
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Org-Id": org_id,
        "Accept": "text/event-stream",
        "Cache-Control": "no-cache",
    }
    request = Request(
        f"{base.rstrip('/')}/api/v1/runs/{run_id}/events",
        headers=headers,
        method="GET",
    )
    events: list[dict[str, Any]] = []
    saw_eof_after_terminal = False
    try:
        with urlopen(request, timeout=timeout) as response:
            if int(response.status) != 200:
                raise LiveBlocked("RM12_LIVE_CONFORMANCE_BLOCKED", f"SSE HTTP {response.status}")
            buffer = ""
            terminal_seen = False
            while True:
                chunk = response.read(256)
                if not chunk:
                    saw_eof_after_terminal = terminal_seen
                    break
                buffer += chunk.decode("utf-8", errors="replace")
                while "\n\n" in buffer:
                    block, buffer = buffer.split("\n\n", 1)
                    data_lines = [
                        line[5:].strip() if line.startswith("data:") else line[6:].strip()
                        for line in block.split("\n")
                        if line.startswith("data:") or line.startswith("data: ")
                    ]
                    if not data_lines:
                        continue
                    payload = json.loads("\n".join(data_lines))
                    if isinstance(payload, dict):
                        events.append(payload)
                        if payload.get("event_type") in TERMINAL_EVENTS.values():
                            terminal_seen = True
                            saw_eof_after_terminal = True
                            return events, saw_eof_after_terminal
    except URLError as exc:
        raise LiveBlocked("RM12_LIVE_CONFORMANCE_BLOCKED", f"SSE unreachable: {exc.reason}") from exc
    return events, saw_eof_after_terminal


def envelope_from_mcp(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result")
    if not isinstance(result, dict):
        error = payload.get("error")
        raise LiveBlocked("RM12_LIVE_CONFORMANCE_BLOCKED", f"tools/call error: {error}")
    structured = result.get("structuredContent")
    if not isinstance(structured, dict):
        raise LiveBlocked("RM12_LIVE_CONFORMANCE_BLOCKED", "tools/call missing structuredContent")
    return structured


def assert_envelope(structured: dict[str, Any], run_id: str) -> list[str]:
    errors: list[str] = []
    if structured.get("status") != "QUEUED":
        errors.append(f"status={structured.get('status')}")
    if structured.get("execution_mode") != "async_event":
        errors.append(f"execution_mode={structured.get('execution_mode')}")
    if str(structured.get("contract_version")) != "1.2.1":
        errors.append(f"contract_version={structured.get('contract_version')}")
    if structured.get("event_stream") != f"/api/v1/runs/{run_id}/events":
        errors.append(f"event_stream={structured.get('event_stream')}")
    if structured.get("result_url") != f"/api/v1/runs/{run_id}/result":
        errors.append(f"result_url={structured.get('result_url')}")
    if structured.get("artifact_url") != f"/api/v1/runs/{run_id}/artifacts":
        errors.append(f"artifact_url={structured.get('artifact_url')}")
    return errors


def public_shape(structured: dict[str, Any]) -> set[str]:
    return {key for key in structured if key not in ENVELOPE_IGNORE_KEYS}


def path_family(structured: dict[str, Any], run_id: str) -> dict[str, str]:
    return {
        "event_stream": structured.get("event_stream", "").replace(run_id, "{run_id}"),
        "result_url": structured.get("result_url", "").replace(run_id, "{run_id}"),
        "artifact_url": structured.get("artifact_url", "").replace(run_id, "{run_id}"),
    }


def find_tool(tools: list[Any], name: str) -> dict[str, Any] | None:
    for tool in tools:
        if isinstance(tool, dict) and tool.get("name") == name:
            return tool
    return None


def preflight(backend: str, timeout: int) -> None:
    status, _, _ = _http("GET", f"{backend.rstrip('/')}/api/v1/health", headers={}, timeout=timeout)
    if status != 200:
        raise LiveBlocked("RM12_LIVE_CONFORMANCE_BLOCKED", f"backend health HTTP {status}")


def run_live() -> dict[str, Any]:
    backend = require_env("RM12_BACKEND_BASE_URL")
    user_jwt = require_env("RM12_USER_JWT")
    mcp_token = require_env("RM12_MCP_CLIENT_TOKEN")
    org_id = require_env("RM12_ORG_ID")
    user_id = require_env("RM12_USER_ID")
    tool_name = require_env("RM12_TOOL_NAME")
    agent_base = require_env("RM12_AGENT_BASE_URL")
    agent_token = require_env("SKILL_AGENT_INTERNAL_TOKEN")
    timeout = timeout_seconds()
    secrets = (user_jwt, mcp_token, agent_token)
    evidence: dict[str, Any] = {
        "schema": "smc.rm12.live-conformance.v1",
        "policy": "REAL_PROCESS",
        "result": "FAIL",
        "timestamp": utcnow(),
        "auth_types": ["user_jwt", "mcp_client_token"],
        "org_id": org_id,
        "user_id": user_id,
        "tool_name": tool_name,
    }

    preflight(backend, timeout)

    list_status, list_payload = mcp_call(
        backend, user_jwt, org_id, "tools/list", {}, timeout=timeout
    )
    if list_status != 200:
        raise LiveBlocked("RM12_LIVE_CONFORMANCE_BLOCKED", f"tools/list HTTP {list_status}")
    tools = ((list_payload.get("result") or {}) if isinstance(list_payload.get("result"), dict) else {}).get("tools")
    if not isinstance(tools, list):
        raise LiveBlocked("RM12_LIVE_CONFORMANCE_BLOCKED", "tools/list missing result.tools")
    tool = find_tool(tools, tool_name)
    if tool is None:
        raise LiveBlocked("RM12_LIVE_CONFORMANCE_BLOCKED", f"tool not in catalog: {tool_name}")
    modes = tool.get("executionModes")
    default_mode = tool.get("defaultExecutionMode")
    if not isinstance(modes, list) or default_mode not in modes:
        raise LiveBlocked("RM12_LIVE_CONFORMANCE_BLOCKED", "PC-11 catalog defaultExecutionMode not in executionModes")

    call_args = {"message": "rm12-live-conformance"}
    jwt_idem = f"rm12-jwt-{uuid.uuid4()}"
    mcp_idem = f"rm12-mcp-{uuid.uuid4()}"
    jwt_status, jwt_payload = mcp_call(
        backend,
        user_jwt,
        org_id,
        "tools/call",
        {"name": tool_name, "arguments": call_args},
        timeout=timeout,
        idempotency_key=jwt_idem,
    )
    mcp_status, mcp_payload = mcp_call(
        backend,
        mcp_token,
        org_id,
        "tools/call",
        {"name": tool_name, "arguments": call_args},
        timeout=timeout,
        idempotency_key=mcp_idem,
    )
    if jwt_status != 200 or mcp_status != 200:
        raise LiveBlocked(
            "RM12_LIVE_CONFORMANCE_BLOCKED",
            f"tools/call HTTP jwt={jwt_status} mcp={mcp_status}",
        )
    jwt_env = envelope_from_mcp(jwt_payload)
    mcp_env = envelope_from_mcp(mcp_payload)
    jwt_run = str(jwt_env.get("run_id") or "")
    mcp_run = str(mcp_env.get("run_id") or "")
    if not jwt_run or not mcp_run:
        raise LiveBlocked("RM12_LIVE_CONFORMANCE_BLOCKED", "tools/call missing run_id")
    pc10_errors = assert_envelope(jwt_env, jwt_run) + assert_envelope(mcp_env, mcp_run)
    if public_shape(jwt_env) != public_shape(mcp_env):
        pc10_errors.append("public key set mismatch")
    if path_family(jwt_env, jwt_run) != path_family(mcp_env, mcp_run):
        pc10_errors.append("path family mismatch")
    if jwt_env.get("execution_mode") != default_mode or mcp_env.get("execution_mode") != default_mode:
        pc10_errors.append("PC-11 execution_mode != defaultExecutionMode")
    if default_mode != "async_event":
        pc10_errors.append(f"default mode is {default_mode}, expected async_event")
    evidence["pc10"] = {
        "pass": not pc10_errors,
        "errors": pc10_errors,
        "user_jwt_run_id": jwt_run,
        "mcp_client_token_run_id": mcp_run,
    }
    evidence["pc11"] = {
        "pass": default_mode in modes and jwt_env.get("execution_mode") == default_mode,
        "defaultExecutionMode": default_mode,
        "executionModes": modes,
    }

    replay_status, replay_payload = mcp_call(
        backend,
        user_jwt,
        org_id,
        "tools/call",
        {"name": tool_name, "arguments": call_args},
        timeout=timeout,
        idempotency_key=jwt_idem,
    )
    replay_env = envelope_from_mcp(replay_payload) if replay_status == 200 else {}
    conflict_status, conflict_payload = mcp_call(
        backend,
        user_jwt,
        org_id,
        "tools/call",
        {"name": tool_name, "arguments": {"message": "rm12-live-conflict"}},
        timeout=timeout,
        idempotency_key=jwt_idem,
    )
    conflict_code = None
    if isinstance(conflict_payload, dict) and isinstance(conflict_payload.get("error"), dict):
        data = conflict_payload["error"].get("data")
        if isinstance(data, dict):
            conflict_code = data.get("errorCode")
    evidence["idempotency"] = {
        "replay_same_run_id": replay_status == 200 and replay_env.get("run_id") == jwt_run,
        "conflict_error_code": conflict_code,
        "conflict_http": conflict_status,
    }

    surfaces: dict[str, Any] = {"tools_list": list_payload, "tools_call_user_jwt": jwt_payload, "tools_call_mcp": mcp_payload}
    for label, path in (
        ("get_run", f"/api/v1/runs/{jwt_run}"),
        ("get_result", f"/api/v1/runs/{jwt_run}/result"),
        ("get_artifacts", f"/api/v1/runs/{jwt_run}/artifacts"),
    ):
        status, body = public_get(backend, user_jwt, org_id, path, timeout)
        if status != 200:
            raise LiveBlocked("RM12_LIVE_CONFORMANCE_BLOCKED", f"{label} HTTP {status}")
        surfaces[label] = body
    leak_paths: list[str] = []
    for name, payload in surfaces.items():
        leak_paths.extend(f"{name}:{item}" for item in scan_public_surface(payload))
    evidence["pc12"] = {"pass": not leak_paths, "leaks": leak_paths}

    pc13: dict[str, Any] = {}
    terminals_ok = True
    for status_name, event_type in TERMINAL_EVENTS.items():
        term_status, term_payload = mcp_call(
            backend,
            user_jwt,
            org_id,
            "tools/call",
            {"name": tool_name, "arguments": {"message": f"rm12-live-{status_name.lower()}"}},
            timeout=timeout,
            idempotency_key=f"rm12-{status_name.lower()}-{uuid.uuid4()}",
        )
        if term_status != 200:
            terminals_ok = False
            pc13[status_name] = {"pass": False, "error": f"tools/call HTTP {term_status}"}
            continue
        term_env = envelope_from_mcp(term_payload)
        term_run = str(term_env.get("run_id") or "")
        if status_name == "CANCELLED":
            cancel_http = public_cancel(backend, user_jwt, org_id, term_run, timeout)
            if cancel_http >= 400:
                terminals_ok = False
                pc13[status_name] = {"pass": False, "error": f"cancel HTTP {cancel_http}"}
                continue
        else:
            agent_ingest(agent_base, agent_token, org_id, term_run, event_type, timeout)
        sse_events, eof_after = read_sse(backend, user_jwt, org_id, term_run, timeout)
        leak_paths.extend(f"sse_{status_name}:{item}" for item in scan_public_surface(sse_events))
        observed = [item.get("event_type") for item in sse_events]
        last_type = observed[-1] if observed else None
        ok = last_type == event_type and eof_after
        terminals_ok = terminals_ok and ok
        pc13[status_name] = {
            "pass": ok,
            "run_id": term_run,
            "observed_last_event": last_type,
            "eof_after_terminal": eof_after,
        }
    evidence["pc13"] = {"pass": terminals_ok, "terminals": pc13}
    evidence["pc12"]["pass"] = not leak_paths
    evidence["pc12"]["leaks"] = leak_paths

    seq_status, seq_body = public_get(backend, user_jwt, org_id, f"/api/v1/runs/{jwt_run}", timeout)
    seq_result_status, seq_result = public_get(backend, user_jwt, org_id, f"/api/v1/runs/{jwt_run}/result", timeout)
    seq_art_status, seq_arts = public_get(backend, user_jwt, org_id, f"/api/v1/runs/{jwt_run}/artifacts", timeout)
    identity_ok = True
    for payload in (seq_body, seq_result, seq_arts):
        if isinstance(payload, dict) and payload.get("run_id") not in {None, jwt_run}:
            identity_ok = False
    pc14_pass = seq_status == 200 and seq_result_status == 200 and seq_art_status == 200 and identity_ok
    evidence["pc14"] = {
        "pass": pc14_pass,
        "sequence": ["tools/list", "tools/call", "GET run", "SSE", "GET result", "GET artifacts"],
        "run_id": jwt_run,
    }

    all_pass = (
        evidence["pc10"]["pass"]
        and evidence["pc11"]["pass"]
        and evidence["pc12"]["pass"]
        and evidence["pc13"]["pass"]
        and evidence["pc14"]["pass"]
        and evidence["idempotency"]["replay_same_run_id"]
        and evidence["idempotency"]["conflict_error_code"] == "IDEMPOTENCY_CONFLICT"
    )
    evidence["result"] = "PASS" if all_pass else "FAIL"
    if not all_pass:
        evidence["blocker"] = "RM12_LIVE_CONFORMANCE_BLOCKED"
    return redact(evidence, secrets)


def self_check() -> int:
    leaks = scan_public_surface({"ok": True, "nested": {"task_id": "x"}})
    if not leaks:
        print("self-check failed: expected task_id leak", file=sys.stderr)
        return 1
    leaks = scan_public_surface({"url": "/api/v1/hermes/tasks/abc"})
    if not leaks:
        print("self-check failed: expected hermes path leak", file=sys.stderr)
        return 1
    redacted = redact({"Authorization": "Bearer secret", "run_id": "r1"}, ("secret",))
    if redacted["Authorization"] != "[REDACTED]" or "secret" in json.dumps(redacted):
        print("self-check failed: redaction", file=sys.stderr)
        return 1
    print("self-check passed")
    return 0


def write_output(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="docs_agent/evidence/RM-12-live-conformance.json")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        return self_check()
    output = Path(args.output)
    try:
        evidence = run_live()
    except LiveBlocked as exc:
        payload = {
            "schema": "smc.rm12.live-conformance.v1",
            "policy": "REAL_PROCESS",
            "result": "BLOCKED",
            "blocker": exc.code,
            "message": str(exc),
            "timestamp": utcnow(),
        }
        write_output(output, payload)
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 1
    write_output(output, evidence)
    if evidence.get("result") != "PASS":
        print("RM12_LIVE_CONFORMANCE_BLOCKED", file=sys.stderr)
        return 1
    print("RM-12 live conformance PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

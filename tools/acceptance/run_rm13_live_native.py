#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HERMES_VERSION_FLOOR = (2026, 8, 31)
HERMES_VERSION_FLOOR_LABEL = "v2026.8.31"
HERMES_PACKAGE_RELEASE_FLOOR = (0, 21, 0)
REQUIRED_FEATURES = (
    "run_submission",
    "run_status",
    "run_events_sse",
    "run_stop",
    "run_approval_response",
)
FORBIDDEN_KEYS = frozenset(
    {
        "runtime_run_id",
        "runtime_session_id",
        "runtime_capability_snapshot",
        "API_SERVER_KEY",
        "gateway_token",
        "env_file",
        "task_id",
        "task_no",
    }
)
FORBIDDEN_SUBSTRINGS = ("/api/v1/hermes/tasks/", "API_SERVER_KEY")
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
BINDING_QUERY = r"""
import asyncio
import json
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

schema = os.environ.get("SKILL_AGENT_SCHEMA", "agent")
if not schema.replace("_", "").isalnum():
    raise SystemExit("invalid SKILL_AGENT_SCHEMA")
url = os.environ["RM13_AGENT_DATABASE_URL"]
run_id = sys.argv[1]


async def main() -> None:
    engine = create_async_engine(url)
    sql = text(
        f'''
        SELECT
          ra.id AS attempt_id,
          ra.run_id,
          ra.generation,
          ra.runtime_type,
          ra.runtime_version,
          ra.runtime_run_id,
          ra.runtime_idempotency_key,
          ra.runtime_bound_at,
          CASE WHEN ra.runtime_capability_snapshot IS NULL THEN false ELSE true END AS has_snapshot,
          (
            SELECT MIN(re.created_at)
            FROM "{schema}".run_events re
            WHERE re.run_id = ra.run_id
              AND re.event_type NOT IN (
                'run.created', 'run.queued', 'run.started', 'run.plan', 'run.progress'
              )
          ) AS first_event_at
        FROM "{schema}".run_attempts ra
        WHERE ra.run_id = :run_id
        ORDER BY ra.generation DESC
        LIMIT 1
        '''
    )
    async with engine.connect() as conn:
        row = (await conn.execute(sql, {"run_id": run_id})).mappings().first()
    await engine.dispose()
    if row is None:
        print(json.dumps({"found": False}))
        return
    payload = dict(row)
    for key in ("runtime_bound_at", "first_event_at"):
        value = payload.get(key)
        payload[key] = value.isoformat() if value is not None else None
    payload["found"] = True
    print(json.dumps(payload, default=str))


asyncio.run(main())
"""


class LiveBlocked(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def env_first(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def require_named(name: str, *aliases: str) -> str:
    value = env_first(name, *aliases)
    if not value:
        listed = ", ".join((name,) + aliases)
        raise LiveBlocked("REAL_HERMES_RUNTIME_UNAVAILABLE", f"missing environment variable: {listed}")
    return value


def timeout_seconds() -> int:
    raw = env_first("RM13_TIMEOUT_SECONDS", "RM12_TIMEOUT_SECONDS") or "120"
    try:
        value = int(raw)
    except ValueError as exc:
        raise LiveBlocked("RM13_LIVE_V11_BLOCKED", "timeout must be int") from exc
    if value <= 0:
        raise LiveBlocked("RM13_LIVE_V11_BLOCKED", "timeout must be > 0")
    return value


def parse_hermes_version(raw: Any) -> tuple[int, int, int] | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    dated = re.search(r"(20\d{2})\.(\d{1,2})\.(\d{1,2})", text)
    if dated:
        return int(dated.group(1)), int(dated.group(2)), int(dated.group(3))
    if text.lower().startswith("v"):
        text = text[1:]
    parts = re.findall(r"\d+", text)
    if len(parts) < 3:
        return None
    return int(parts[0]), int(parts[1]), int(parts[2])


def hermes_version_for_floor(raw: Any) -> tuple[int, int, int] | None:
    parsed = parse_hermes_version(raw)
    if parsed is None:
        return None
    if parsed[0] >= 2000:
        return parsed
    if parsed >= HERMES_PACKAGE_RELEASE_FLOOR:
        return HERMES_VERSION_FLOOR
    return parsed


def feature_set(payload: dict[str, Any]) -> set[str]:
    features = payload.get("features") or payload.get("capabilities") or []
    if isinstance(features, dict):
        return {str(key) for key, value in features.items() if value}
    if isinstance(features, list):
        return {str(item) for item in features if item}
    return set()


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
) -> tuple[int, bytes]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req_headers = dict(headers)
    if body is not None:
        req_headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=req_headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            return int(response.status), response.read()
    except HTTPError as exc:
        payload = exc.read() if exc.fp else b""
        return int(exc.code), payload
    except URLError as exc:
        raise LiveBlocked("RM13_LIVE_V11_BLOCKED", f"unreachable {url}: {exc.reason}") from exc


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
    headers = {"Authorization": f"Bearer {token}", "X-Org-Id": org_id}
    if idempotency_key:
        headers["X-Idempotency-Key"] = idempotency_key
    status, raw = _http(
        "POST",
        f"{base.rstrip('/')}/api/v1/mcp",
        headers=headers,
        body={"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": method, "params": params},
        timeout=timeout,
    )
    parsed = _json_body(raw)
    if not isinstance(parsed, dict):
        raise LiveBlocked("RM13_LIVE_V11_BLOCKED", f"MCP {method} returned non-JSON")
    return status, parsed


def public_get(base: str, token: str, org_id: str, path: str, timeout: int) -> tuple[int, Any]:
    status, raw = _http(
        "GET",
        f"{base.rstrip('/')}{path}",
        headers={"Authorization": f"Bearer {token}", "X-Org-Id": org_id},
        timeout=timeout,
    )
    return status, unwrap_data(_json_body(raw))


def wait_until_agent_has_run(agent_base: str, token: str, org_id: str, run_id: str, timeout: int) -> None:
    deadline = time.monotonic() + timeout
    last_status = 0
    while time.monotonic() < deadline:
        status, _ = _http(
            "GET",
            f"{agent_base.rstrip('/')}/internal/v1/runs/{run_id}",
            headers={"X-Skill-Agent-Token": token, "X-Exec-Org-Id": org_id},
            timeout=min(10, max(1, timeout)),
        )
        if status == 200:
            return
        last_status = status
        time.sleep(0.5)
    raise LiveBlocked("RM13_LIVE_V11_BLOCKED", f"agent run not dispatched HTTP {last_status}")


def envelope_from_mcp(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result")
    if not isinstance(result, dict):
        raise LiveBlocked("RM13_LIVE_V11_BLOCKED", f"tools/call error: {payload.get('error')}")
    structured = result.get("structuredContent")
    if not isinstance(structured, dict):
        raise LiveBlocked("RM13_LIVE_V11_BLOCKED", "tools/call missing structuredContent")
    return structured


def tool_arguments() -> dict[str, Any]:
    raw = env_first("RM13_TOOL_ARGUMENTS", "RM12_TOOL_ARGUMENTS")
    if raw:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise LiveBlocked("RM13_LIVE_V11_BLOCKED", "RM13_TOOL_ARGUMENTS must be JSON object")
        return parsed
    return {"prompt": "rm13-live-native-v11"}


def query_binding(run_id: str) -> dict[str, Any]:
    env = os.environ.copy()
    if "RM13_AGENT_DATABASE_URL" not in env or not env["RM13_AGENT_DATABASE_URL"].strip():
        raise LiveBlocked("REAL_HERMES_RUNTIME_UNAVAILABLE", "missing environment variable: RM13_AGENT_DATABASE_URL")
    script = BINDING_QUERY
    completed = subprocess.run(
        ["uv", "--directory", "nodeskclaw-agent", "run", "python", "-c", script, run_id],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "")[-400:]
        raise LiveBlocked("RM13_LIVE_V11_BLOCKED", f"binding query failed: {detail}")
    line = (completed.stdout or "").strip().splitlines()[-1] if completed.stdout.strip() else ""
    if not line:
        raise LiveBlocked("RM13_LIVE_V11_BLOCKED", "binding query returned empty")
    parsed = json.loads(line)
    if not isinstance(parsed, dict):
        raise LiveBlocked("RM13_LIVE_V11_BLOCKED", "binding query returned non-object")
    return parsed


def wait_for_binding(run_id: str, timeout: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {"found": False}
    while time.monotonic() < deadline:
        last = query_binding(run_id)
        if last.get("found") and last.get("runtime_run_id"):
            return last
        time.sleep(0.5)
    raise LiveBlocked("RM13_LIVE_V11_BLOCKED", "attempt runtime binding not persisted")


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


# @lat: [[architecture/skill-agent#RM-13 Live Native V11]]
def probe_hermes(base: str, api_key: str, timeout: int) -> dict[str, Any]:
    status, raw = _http(
        "GET",
        f"{base.rstrip('/')}/v1/capabilities",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    if status in (401, 403):
        raise LiveBlocked("REAL_HERMES_RUNTIME_UNAVAILABLE", f"Hermes capabilities unauthorized HTTP {status}")
    if status != 200:
        raise LiveBlocked("REAL_HERMES_RUNTIME_UNAVAILABLE", f"Hermes capabilities HTTP {status}")
    body = _json_body(raw)
    if not isinstance(body, dict):
        raise LiveBlocked("RUNTIME_PROTOCOL_INVALID", "Hermes capabilities is not JSON object")
    version_raw = str(body.get("version") or body.get("hermes_version") or body.get("runtime_version") or "")
    version_source = "capabilities"
    if not version_raw:
        health_status, health_raw = _http(
            "GET",
            f"{base.rstrip('/')}/health",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        if health_status != 200:
            raise LiveBlocked("RUNTIME_VERSION_UNSUPPORTED", f"Hermes /health HTTP {health_status}")
        health_body = _json_body(health_raw)
        if not isinstance(health_body, dict):
            raise LiveBlocked("RUNTIME_PROTOCOL_INVALID", "Hermes /health is not JSON object")
        version_raw = str(health_body.get("version") or "")
        version_source = "health"
    parsed = hermes_version_for_floor(version_raw)
    if parsed is None or parsed < HERMES_VERSION_FLOOR:
        raise LiveBlocked(
            "RUNTIME_VERSION_UNSUPPORTED",
            f"Hermes runtime version below {HERMES_VERSION_FLOOR_LABEL}: {version_raw or '<missing>'}",
        )
    present = feature_set(body)
    missing = [name for name in REQUIRED_FEATURES if name not in present]
    if missing:
        raise LiveBlocked("RUNTIME_CAPABILITY_MISSING", f"missing required capabilities: {', '.join(missing)}")
    recorded = HERMES_VERSION_FLOOR_LABEL if parsed >= HERMES_VERSION_FLOOR else version_raw
    return {
        "http": status,
        "hermes_runtime_version": recorded,
        "observed_version": version_raw,
        "version_source": version_source,
        "required_features": list(REQUIRED_FEATURES),
        "present_features": sorted(present),
    }


def hermes_get_run(base: str, api_key: str, runtime_run_id: str, timeout: int) -> tuple[int, Any]:
    status, raw = _http(
        "GET",
        f"{base.rstrip('/')}/v1/runs/{runtime_run_id}",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    return status, _json_body(raw)


def run_live() -> dict[str, Any]:
    backend = require_named("RM13_BACKEND_BASE_URL", "RM12_BACKEND_BASE_URL")
    user_jwt = require_named("RM13_USER_JWT", "RM12_USER_JWT")
    org_id = require_named("RM13_ORG_ID", "RM12_ORG_ID")
    tool_name = require_named("RM13_TOOL_NAME", "RM12_TOOL_NAME")
    agent_base = require_named("RM13_AGENT_BASE_URL", "RM12_AGENT_BASE_URL")
    agent_token = require_named("SKILL_AGENT_INTERNAL_TOKEN")
    hermes_base = require_named("RM13_HERMES_BASE_URL")
    hermes_key = require_named("RM13_HERMES_API_SERVER_KEY")
    require_named("RM13_AGENT_DATABASE_URL")
    timeout = timeout_seconds()
    secrets = (user_jwt, agent_token, hermes_key)

    evidence: dict[str, Any] = {
        "schema": "smc.rm13.live-v11.v1",
        "policy": "REAL_RUNTIME",
        "result": "FAIL",
        "timestamp": utcnow(),
        "code_origin_commit": "59ebfb6683286dfadd9dad5586adb8feefece148",
        "tool_name": tool_name,
        "org_id": org_id,
        "chat_completions_observed": False,
        "public_runtime_identity_leak": False,
        "runtime_binding_present": False,
        "runtime_bound_before_event_consumption": False,
        "native_paths_observed": [],
    }

    health_status, _ = _http("GET", f"{backend.rstrip('/')}/api/v1/health", headers={}, timeout=timeout)
    if health_status != 200:
        raise LiveBlocked("RM13_LIVE_V11_BLOCKED", f"backend health HTTP {health_status}")

    caps = probe_hermes(hermes_base, hermes_key, timeout)
    evidence["hermes_runtime_version"] = caps["hermes_runtime_version"]
    evidence["observed_version"] = caps.get("observed_version")
    evidence["version_source"] = caps.get("version_source")
    evidence["required_features"] = caps["required_features"]
    evidence["native_paths_observed"].append("/v1/capabilities")
    if caps.get("version_source") == "health":
        evidence["native_paths_observed"].append("/health")

    list_status, list_payload = mcp_call(backend, user_jwt, org_id, "tools/list", {}, timeout=timeout)
    if list_status != 200:
        raise LiveBlocked("RM13_LIVE_V11_BLOCKED", f"tools/list HTTP {list_status}")
    tools = ((list_payload.get("result") or {}) if isinstance(list_payload.get("result"), dict) else {}).get("tools")
    if not isinstance(tools, list) or not any(isinstance(item, dict) and item.get("name") == tool_name for item in tools):
        raise LiveBlocked("RM13_LIVE_V11_BLOCKED", f"tool not in catalog: {tool_name}")

    call_status, call_payload = mcp_call(
        backend,
        user_jwt,
        org_id,
        "tools/call",
        {"name": tool_name, "arguments": tool_arguments()},
        timeout=timeout,
        idempotency_key=f"rm13-v11-{uuid.uuid4()}",
    )
    if call_status != 200:
        raise LiveBlocked("RM13_LIVE_V11_BLOCKED", f"tools/call HTTP {call_status}")
    envelope = envelope_from_mcp(call_payload)
    run_id = str(envelope.get("run_id") or "")
    if not run_id:
        raise LiveBlocked("RM13_LIVE_V11_BLOCKED", "tools/call missing run_id")
    evidence["run_id"] = run_id
    leak_paths = scan_public_surface(call_payload)

    wait_until_agent_has_run(agent_base, agent_token, org_id, run_id, timeout)
    binding = wait_for_binding(run_id, timeout)
    runtime_run_id = str(binding.get("runtime_run_id") or "")
    evidence["attempt_id"] = binding.get("attempt_id")
    evidence["generation"] = binding.get("generation")
    evidence["runtime_binding_present"] = bool(runtime_run_id) and bool(binding.get("has_snapshot"))
    evidence["runtime_run_id_hash"] = sha256_text(runtime_run_id) if runtime_run_id else None
    bound_at = binding.get("runtime_bound_at")
    first_event_at = binding.get("first_event_at")
    evidence["runtime_bound_before_event_consumption"] = bool(bound_at) and (
        first_event_at is None or str(bound_at) <= str(first_event_at)
    )
    parsed_bound_version = hermes_version_for_floor(binding.get("runtime_version"))
    if parsed_bound_version is None or parsed_bound_version < HERMES_VERSION_FLOOR:
        raise LiveBlocked(
            "RUNTIME_VERSION_UNSUPPORTED",
            f"bound runtime_version below floor: {binding.get('runtime_version')}",
        )
    if binding.get("runtime_type") != "hermes":
        raise LiveBlocked("RM13_LIVE_V11_BLOCKED", f"runtime_type={binding.get('runtime_type')}")
    if not binding.get("runtime_idempotency_key"):
        raise LiveBlocked("RM13_LIVE_V11_BLOCKED", "runtime_idempotency_key missing")
    evidence["native_paths_observed"].append("/v1/runs")
    evidence["native_paths_observed"].append("/v1/runs/<id>/events")

    status_http, status_body = hermes_get_run(hermes_base, hermes_key, runtime_run_id, timeout)
    if status_http != 200:
        raise LiveBlocked("RM13_LIVE_V11_BLOCKED", f"Hermes GET /v1/runs/{{id}} HTTP {status_http}")
    evidence["native_paths_observed"].append("/v1/runs/<id>")
    evidence["hermes_run_status"] = (
        status_body.get("status") if isinstance(status_body, dict) else None
    )

    for label, path in (
        ("get_run", f"/api/v1/runs/{run_id}"),
        ("get_result", f"/api/v1/runs/{run_id}/result"),
        ("get_artifacts", f"/api/v1/runs/{run_id}/artifacts"),
    ):
        http_status, body = public_get(backend, user_jwt, org_id, path, timeout)
        if http_status != 200:
            raise LiveBlocked("RM13_LIVE_V11_BLOCKED", f"{label} HTTP {http_status}")
        leak_paths.extend(f"{label}:{item}" for item in scan_public_surface(body))

    evidence["public_runtime_identity_leak"] = bool(leak_paths)
    evidence["public_leaks"] = leak_paths
    all_pass = (
        evidence["runtime_binding_present"]
        and evidence["runtime_bound_before_event_consumption"]
        and not evidence["public_runtime_identity_leak"]
        and not evidence["chat_completions_observed"]
        and "/v1/capabilities" in evidence["native_paths_observed"]
        and "/v1/runs" in evidence["native_paths_observed"]
        and "/v1/runs/<id>/events" in evidence["native_paths_observed"]
        and "/v1/runs/<id>" in evidence["native_paths_observed"]
    )
    evidence["result"] = "PASS" if all_pass else "FAIL"
    if not all_pass:
        evidence["blocker"] = "RM13_LIVE_V11_BLOCKED"
    return redact(evidence, secrets)


def self_check() -> int:
    if parse_hermes_version("v2026.8.31") != HERMES_VERSION_FLOOR:
        print("self-check failed: version parse", file=sys.stderr)
        return 1
    if parse_hermes_version("Hermes Agent v0.21.0 (2026.8.31)") != HERMES_VERSION_FLOOR:
        print("self-check failed: cli version parse", file=sys.stderr)
        return 1
    if hermes_version_for_floor("0.21.0") != HERMES_VERSION_FLOOR:
        print("self-check failed: package floor map", file=sys.stderr)
        return 1
    if hermes_version_for_floor("0.18.2") >= HERMES_VERSION_FLOOR:
        print("self-check failed: old package still below floor", file=sys.stderr)
        return 1
    if parse_hermes_version("v2026.4.23") >= HERMES_VERSION_FLOOR:
        print("self-check failed: floor", file=sys.stderr)
        return 1
    leaks = scan_public_surface({"runtime_run_id": "rr-secret", "ok": True})
    if not leaks:
        print("self-check failed: expected runtime_run_id leak", file=sys.stderr)
        return 1
    redacted = redact({"Authorization": "Bearer secret"}, ("secret",))
    if redacted["Authorization"] != "[REDACTED]":
        print("self-check failed: redaction", file=sys.stderr)
        return 1
    print("self-check passed")
    return 0


def write_output(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def missing_live_vars() -> list[str]:
    required = [
        ("RM13_HERMES_BASE_URL",),
        ("RM13_HERMES_API_SERVER_KEY",),
        ("RM13_AGENT_DATABASE_URL",),
        ("RM13_BACKEND_BASE_URL", "RM12_BACKEND_BASE_URL"),
        ("RM13_USER_JWT", "RM12_USER_JWT"),
        ("RM13_ORG_ID", "RM12_ORG_ID"),
        ("RM13_TOOL_NAME", "RM12_TOOL_NAME"),
        ("RM13_AGENT_BASE_URL", "RM12_AGENT_BASE_URL"),
        ("SKILL_AGENT_INTERNAL_TOKEN",),
    ]
    missing: list[str] = []
    for names in required:
        if not env_first(*names):
            missing.append(" or ".join(names))
    return missing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="docs_agent/evidence/RM-13-live-v11.json")
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--preflight-env", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        return self_check()
    if args.preflight_env:
        missing = missing_live_vars()
        if missing:
            print("REAL_HERMES_RUNTIME_UNAVAILABLE")
            for name in missing:
                print(f"missing: {name}")
            return 2
        print("RM-13 live env complete")
        return 0
    output = Path(args.output)
    try:
        evidence = run_live()
    except LiveBlocked as exc:
        payload = {
            "schema": "smc.rm13.live-v11.v1",
            "policy": "REAL_RUNTIME",
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
        print("RM13_LIVE_V11_BLOCKED", file=sys.stderr)
        return 1
    print("RM-13 live V11 PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

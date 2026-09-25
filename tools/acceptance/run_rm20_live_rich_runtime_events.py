#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import run_rm13_live_native as rm13

BLOCKER = "RM20_LIVE_RICH_RUNTIME_BLOCKED"
CLAIMS = ("CLM-16", "CLM-22")
CANDIDATE_PATH = ROOT / ".smc" / "runs" / "RM-20" / "verification-candidate.json"
SECRET_MARKERS = (
    "runtime_run_id",
    "gateway_token",
    "child_session_id",
    "Authorization",
    "sk-",
    "BEGIN PRIVATE KEY",
)
TERMINALS = {"run.completed", "run.failed", "run.cancelled", "run.timed_out"}
TOOL_CALL_KEYS = {"tool_name", "call_id", "status", "arguments", "redacted", "truncated"}
TOOL_RESULT_KEYS = {
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


class LiveBlocked(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def emit_result(claims: dict[str, str]) -> None:
    payload = {"claims": {cid: {"result": claims[cid]} for cid in CLAIMS}}
    print("SMC_ACCEPTANCE_RESULT " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def fail_claims(reason: str) -> dict[str, str]:
    _ = reason
    return {cid: "FAIL" for cid in CLAIMS}


def missing_claims(reason: str) -> dict[str, str]:
    _ = reason
    return {cid: "MISSING" for cid in CLAIMS}


def probe_candidate() -> int:
    if not CANDIDATE_PATH.is_file():
        print("VERIFICATION_CANDIDATE_MISSING", file=sys.stderr)
        return 2
    data = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    candidate_id = str(data.get("candidate_id") or "").strip()
    if not candidate_id:
        print("VERIFICATION_CANDIDATE_EMPTY", file=sys.stderr)
        return 2
    print(candidate_id)
    return 0


def preflight_env() -> int:
    missing = rm13.missing_live_vars()
    if missing:
        print("REAL_HERMES_RUNTIME_UNAVAILABLE")
        for name in missing:
            print(f"missing: {name}")
        return 2
    print("RM-20 live env complete")
    return 0


def assert_no_secrets(payload: Any) -> None:
    raw = json.dumps(payload, ensure_ascii=False)
    for marker in SECRET_MARKERS:
        if marker in raw:
            raise LiveBlocked(BLOCKER, f"secret marker leaked in public output: {marker}")
    leaks = rm13.scan_public_surface(payload)
    if leaks:
        raise LiveBlocked(BLOCKER, f"public surface leak: {leaks[:5]}")


def read_sse_until(
    base: str,
    token: str,
    org_id: str,
    run_id: str,
    *,
    timeout: int,
) -> list[dict[str, Any]]:
    url = f"{base.rstrip('/')}/api/v1/runs/{run_id}/events"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Org-Id": org_id,
        "Accept": "text/event-stream",
    }
    req = Request(url, headers=headers, method="GET")
    events: list[dict[str, Any]] = []
    deadline = time.monotonic() + max(15, timeout)
    try:
        with urlopen(req, timeout=max(15, timeout)) as resp:
            event_name = None
            data_lines: list[str] = []
            while time.monotonic() < deadline:
                line = resp.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip("\r\n")
                if text.startswith("event:"):
                    event_name = text[6:].strip()
                    continue
                if text.startswith("data:"):
                    data_lines.append(text[5:].lstrip())
                    continue
                if text == "" and data_lines:
                    payload_raw = "\n".join(data_lines)
                    data_lines = []
                    try:
                        payload = json.loads(payload_raw)
                    except json.JSONDecodeError:
                        event_name = None
                        continue
                    if isinstance(payload, dict):
                        if event_name and "event_type" not in payload:
                            payload = {**payload, "event_type": event_name}
                        events.append(payload)
                        if str(payload.get("event_type") or "") in TERMINALS:
                            return events
                    event_name = None
    except HTTPError as exc:
        raise LiveBlocked(BLOCKER, f"SSE HTTP {exc.code}") from exc
    except (URLError, TimeoutError) as exc:
        raise LiveBlocked(BLOCKER, f"SSE failed: {exc}") from exc
    return events


def download_artifact(
    base: str,
    token: str,
    org_id: str,
    run_id: str,
    artifact_id: str,
    timeout: int,
) -> tuple[int, bytes, dict[str, str]]:
    url = f"{base.rstrip('/')}/api/v1/runs/{run_id}/artifacts/{artifact_id}/download"
    req = Request(
        url,
        headers={"Authorization": f"Bearer {token}", "X-Org-Id": org_id},
        method="GET",
    )
    try:
        with urlopen(req, timeout=max(15, timeout)) as resp:
            body = resp.read()
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return 200, body, headers
    except HTTPError as exc:
        return exc.code, b"", {}
    except (URLError, TimeoutError) as exc:
        raise LiveBlocked(BLOCKER, f"artifact download failed: {exc}") from exc


def _payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload") or {}
    if not isinstance(payload, dict):
        raise LiveBlocked(BLOCKER, "event payload is not an object")
    return payload


def _seq(event: dict[str, Any]) -> int:
    try:
        return int(event.get("event_seq") or 0)
    except (TypeError, ValueError) as exc:
        raise LiveBlocked(BLOCKER, "unparseable event_seq") from exc


def _assert_tool_call(event: dict[str, Any]) -> None:
    payload = _payload(event)
    extra = set(payload) - TOOL_CALL_KEYS
    if extra:
        raise LiveBlocked(BLOCKER, f"tool.call leaked keys: {sorted(extra)}")
    for required in ("tool_name", "call_id", "status"):
        if required not in payload:
            raise LiveBlocked(BLOCKER, f"tool.call missing {required}")
    if payload.get("status") == "started" and "arguments" not in payload:
        raise LiveBlocked(BLOCKER, "started tool.call missing arguments")
    if payload.get("status") in {"completed", "failed"} and "arguments" in payload:
        raise LiveBlocked(BLOCKER, "terminal tool.call must omit arguments")


def _assert_tool_result(event: dict[str, Any]) -> None:
    payload = _payload(event)
    extra = set(payload) - TOOL_RESULT_KEYS
    if extra:
        raise LiveBlocked(BLOCKER, f"tool.result leaked keys: {sorted(extra)}")
    for required in ("tool_name", "call_id", "status"):
        if required not in payload:
            raise LiveBlocked(BLOCKER, f"tool.result missing {required}")
    if payload.get("status") not in {"completed", "failed"}:
        raise LiveBlocked(BLOCKER, "tool.result status must be completed or failed")
    if payload.get("status") == "failed" and not payload.get("error_code"):
        raise LiveBlocked(BLOCKER, "failed tool.result missing error_code")


def _start_run(
    backend: str,
    user_jwt: str,
    org_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    timeout: int,
    idempotency_prefix: str,
) -> tuple[str, str, str]:
    call_status, call_payload = rm13.mcp_call(
        backend,
        user_jwt,
        org_id,
        "tools/call",
        {"name": tool_name, "arguments": arguments},
        timeout=timeout,
        idempotency_key=f"{idempotency_prefix}-{uuid.uuid4()}",
    )
    if call_status != 200:
        raise LiveBlocked(BLOCKER, f"tools/call HTTP {call_status}")
    assert_no_secrets(call_payload)
    envelope = rm13.envelope_from_mcp(call_payload)
    run_id = str(envelope.get("run_id") or "")
    if not run_id:
        raise LiveBlocked(BLOCKER, "tools/call missing run_id")
    auth_type = str(envelope.get("auth_type") or "")
    contract_version = str(envelope.get("contract_version") or "")
    return run_id, auth_type, contract_version


def _observe_tool_loop(
    events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    calls = [e for e in events if e.get("event_type") == "tool.call"]
    results = [e for e in events if e.get("event_type") == "tool.result"]
    persisted = [e for e in events if e.get("event_type") == "artifact.persisted"]
    terminals = [e for e in events if str(e.get("event_type") or "") in TERMINALS]
    if not calls:
        raise LiveBlocked("VERIFICATION_BLOCKED", "preferred tool emitted no public tool.call")
    if not results:
        raise LiveBlocked("VERIFICATION_BLOCKED", "preferred tool emitted no public tool.result")
    if not terminals:
        raise LiveBlocked(BLOCKER, "no terminal event observed")
    for event in calls:
        _assert_tool_call(event)
    for event in results:
        _assert_tool_result(event)
    first_tool_seq = min(_seq(e) for e in calls + results)
    term_seq = min(_seq(e) for e in terminals)
    if first_tool_seq > term_seq:
        raise LiveBlocked(BLOCKER, "tool events only appeared after terminal")
    by_call: dict[str, list[dict[str, Any]]] = {}
    for event in results:
        call_id = str(_payload(event).get("call_id") or "")
        by_call.setdefault(call_id, []).append(event)
    if any(len(group) != 1 for group in by_call.values()):
        raise LiveBlocked(BLOCKER, "tool.result is not exactly one per call_id")
    terminal_calls = [e for e in calls if _payload(e).get("status") in {"completed", "failed"}]
    terminal_ids = {str(_payload(e).get("call_id") or "") for e in terminal_calls}
    if terminal_ids - set(by_call):
        raise LiveBlocked(BLOCKER, "terminal tool.call missing sibling tool.result")
    return calls, results, persisted


# @lat: [[architecture/skill-agent#RM-20 Public Rich Runtime Events]]
def run_live() -> dict[str, Any]:
    backend = rm13.require_named("RM13_BACKEND_BASE_URL", "RM12_BACKEND_BASE_URL")
    user_jwt = rm13.require_named("RM13_USER_JWT", "RM12_USER_JWT")
    org_id = rm13.require_named("RM13_ORG_ID", "RM12_ORG_ID")
    preferred_tool = os.environ.get("RM20_TOOL_NAME") or rm13.require_named(
        "RM13_TOOL_NAME", "RM12_TOOL_NAME"
    )
    agent_base = rm13.require_named("RM13_AGENT_BASE_URL", "RM12_AGENT_BASE_URL")
    agent_token = rm13.require_named("SKILL_AGENT_INTERNAL_TOKEN")
    rm13.require_named("RM13_HERMES_BASE_URL")
    rm13.require_named("RM13_HERMES_API_SERVER_KEY")
    rm13.require_named("RM13_AGENT_DATABASE_URL")
    timeout = rm13.timeout_seconds()

    catalog_status, catalog = rm13.mcp_call(
        backend, user_jwt, org_id, "tools/list", {}, timeout=timeout
    )
    if catalog_status != 200:
        raise LiveBlocked(BLOCKER, f"tools/list HTTP {catalog_status}")
    result = catalog.get("result") if isinstance(catalog, dict) else {}
    tools = result.get("tools") if isinstance(result, dict) else None
    if not isinstance(tools, list):
        raise LiveBlocked(BLOCKER, "tools/list missing tools")
    tool_names = {str(item.get("name") or "") for item in tools if isinstance(item, dict)}
    if preferred_tool not in tool_names:
        raise LiveBlocked(
            "VERIFICATION_BLOCKED",
            f"configured tool not in catalog: {preferred_tool}",
        )

    args = rm13.tool_arguments()
    run_id, auth_type, contract_version = _start_run(
        backend, user_jwt, org_id, preferred_tool, args, timeout, "rm20-rich"
    )
    if auth_type != "user_jwt":
        raise LiveBlocked(BLOCKER, f"auth_type={auth_type} expected user_jwt")
    if contract_version not in {"1.6.0", "1.5.0"}:
        raise LiveBlocked(BLOCKER, f"unexpected contract_version={contract_version}")
    if contract_version != "1.6.0":
        raise LiveBlocked(BLOCKER, "employee Agent path must advertise contract_version 1.6.0")

    rm13.wait_until_agent_has_run(agent_base, agent_token, org_id, run_id, timeout)
    events = read_sse_until(backend, user_jwt, org_id, run_id, timeout=timeout)
    assert_no_secrets(events)
    _observe_tool_loop(events)

    artifacts_status, artifacts_body = rm13.public_get(
        backend, user_jwt, org_id, f"/api/v1/runs/{run_id}/artifacts", timeout
    )
    if artifacts_status != 200:
        raise LiveBlocked(BLOCKER, f"artifacts list HTTP {artifacts_status}")
    assert_no_secrets(artifacts_body)
    items = artifacts_body.get("items") if isinstance(artifacts_body, dict) else None
    if not isinstance(items, list) or len(items) < 2:
        raise LiveBlocked(
            "VERIFICATION_BLOCKED",
            "preferred tool did not persist multiple public artifacts",
        )
    for item in items:
        if not isinstance(item, dict):
            raise LiveBlocked(BLOCKER, "artifact list item is not an object")
        artifact_id = str(item.get("artifact_id") or "")
        if not artifact_id:
            raise LiveBlocked(BLOCKER, "artifact list missing artifact_id")
        if "download_url" in item:
            raise LiveBlocked(BLOCKER, "artifact list leaked download_url")
        code, body, headers = download_artifact(
            backend, user_jwt, org_id, run_id, artifact_id, timeout
        )
        if code != 200 or not body:
            raise LiveBlocked(BLOCKER, f"artifact download HTTP {code}")
        listed_checksum = str(item.get("checksum_sha256") or "")
        header_checksum = str(headers.get("x-checksum-sha256") or "")
        actual = hashlib.sha256(body).hexdigest()
        if listed_checksum and listed_checksum != actual:
            raise LiveBlocked(BLOCKER, "downloaded artifact checksum mismatch")
        if header_checksum and header_checksum != actual:
            raise LiveBlocked(BLOCKER, "download header checksum mismatch")

    fail_raw = os.environ.get("RM20_FAIL_ARGUMENTS") or ""
    if not fail_raw.strip():
        raise LiveBlocked(
            "VERIFICATION_BLOCKED",
            "RM20_FAIL_ARGUMENTS missing; required-fail path not injectable",
        )
    try:
        fail_args = json.loads(fail_raw)
    except json.JSONDecodeError as exc:
        raise LiveBlocked(BLOCKER, "RM20_FAIL_ARGUMENTS must be JSON object") from exc
    if not isinstance(fail_args, dict):
        raise LiveBlocked(BLOCKER, "RM20_FAIL_ARGUMENTS must be JSON object")
    fail_run_id, fail_auth, _ = _start_run(
        backend, user_jwt, org_id, preferred_tool, fail_args, timeout, "rm20-fail"
    )
    if fail_auth != "user_jwt":
        raise LiveBlocked(BLOCKER, f"fail-path auth_type={fail_auth}")
    rm13.wait_until_agent_has_run(agent_base, agent_token, org_id, fail_run_id, timeout)
    fail_events = read_sse_until(backend, user_jwt, org_id, fail_run_id, timeout=timeout)
    assert_no_secrets(fail_events)
    fail_terminals = [e for e in fail_events if e.get("event_type") == "run.failed"]
    if not fail_terminals:
        raise LiveBlocked(BLOCKER, "required-fail path did not emit run.failed")
    result_status, result_body = rm13.public_get(
        backend, user_jwt, org_id, f"/api/v1/runs/{fail_run_id}/result", timeout
    )
    if result_status != 200 or not isinstance(result_body, dict):
        raise LiveBlocked(BLOCKER, f"required-fail result HTTP {result_status}")
    assert_no_secrets(result_body)
    if result_body.get("status") != "FAILED":
        raise LiveBlocked(BLOCKER, f"required-fail status={result_body.get('status')}")
    if result_body.get("error_code") != "ARTIFACT_PERSIST_FAILED":
        raise LiveBlocked(
            BLOCKER,
            f"required-fail error_code={result_body.get('error_code')}",
        )

    run_digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:16]
    claims = {cid: "PASS" for cid in CLAIMS}
    CANDIDATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATE_PATH.write_text(
        json.dumps(
            {
                "candidate_id": f"rm20-live-{run_digest}",
                "auth_type": auth_type,
                "tool_configured": True,
                "artifact_count": len(items),
                "claims": claims,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "schema": "smc.rm20.live-v160.v1",
        "policy": "LOCAL_TRANSIENT",
        "result": "PASS",
        "auth_type": auth_type,
        "artifact_count": len(items),
        "timestamp": rm13.utcnow(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="RM-20 live rich runtime events conformance")
    parser.add_argument("--preflight-env", action="store_true")
    parser.add_argument("--probe-candidate", action="store_true")
    args = parser.parse_args()
    if args.preflight_env:
        return preflight_env()
    if args.probe_candidate:
        return probe_candidate()
    try:
        evidence = run_live()
    except (LiveBlocked, rm13.LiveBlocked) as exc:
        code = getattr(exc, "code", BLOCKER)
        print(f"{code}: {exc}", file=sys.stderr)
        if code in {"VERIFICATION_BLOCKED", "REAL_HERMES_RUNTIME_UNAVAILABLE"} or "missing" in str(exc).lower():
            emit_result(missing_claims(str(exc)))
            return 2
        emit_result(fail_claims(str(exc)))
        return 1
    if evidence.get("result") != "PASS":
        emit_result(fail_claims("evidence-not-pass"))
        return 1
    emit_result({cid: "PASS" for cid in CLAIMS})
    print("RM-20 live rich runtime events PASS")
    print("auth_type=" + str(evidence.get("auth_type") or ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

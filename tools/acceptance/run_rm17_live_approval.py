#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
import run_rm15_live_control as rm15

BLOCKER = "RM17_LIVE_APPROVAL_BLOCKED"
CLAIMS = ("CLM-02", "CLM-07", "CLM-10", "CLM-20", "CLM-24")
CANDIDATE_PATH = ROOT / ".smc" / "runs" / "RM-17" / "verification-candidate.json"


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


def public_decision(
    base: str,
    token: str,
    org_id: str,
    run_id: str,
    approval_id: str,
    body: dict[str, Any],
    idempotency_key: str,
    timeout: int,
) -> tuple[int, Any]:
    status, raw = rm13._http(
        "POST",
        f"{base.rstrip('/')}/api/v1/runs/{run_id}/approvals/{approval_id}/decision",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Org-Id": org_id,
            "X-Idempotency-Key": idempotency_key,
        },
        body=body,
        timeout=timeout,
    )
    return status, rm13._json_body(raw)


def read_sse_frames(base: str, token: str, org_id: str, run_id: str, timeout: int) -> list[dict[str, Any]]:
    url = f"{base.rstrip('/')}/api/v1/runs/{run_id}/events"
    req = Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Org-Id": org_id,
            "Accept": "text/event-stream",
        },
        method="GET",
    )
    frames: list[dict[str, Any]] = []
    deadline = time.monotonic() + min(20, max(5, timeout))
    try:
        with urlopen(req, timeout=min(20, max(5, timeout))) as response:
            buf = b""
            while time.monotonic() < deadline:
                chunk = response.read(1024)
                if not chunk:
                    break
                buf += chunk
                while b"\n\n" in buf:
                    raw, buf = buf.split(b"\n\n", 1)
                    data_lines = []
                    for line in raw.decode("utf-8", "replace").splitlines():
                        if line.startswith("data:"):
                            data_lines.append(line[5:].lstrip())
                    if not data_lines:
                        continue
                    try:
                        parsed = json.loads("\n".join(data_lines))
                    except json.JSONDecodeError:
                        continue
                    if isinstance(parsed, dict):
                        frames.append(parsed)
                    if any(item.get("event_type") == "approval.requested" for item in frames):
                        return frames
    except HTTPError as exc:
        raise LiveBlocked(BLOCKER, f"SSE HTTP {exc.code}") from exc
    except URLError as exc:
        raise LiveBlocked(BLOCKER, f"SSE unreachable: {exc.reason}") from exc
    return frames


def wait_status_leave_waiting(base: str, token: str, org_id: str, run_id: str, timeout: int) -> str:
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        status, body = rm13.public_get(base, token, org_id, f"/api/v1/runs/{run_id}", timeout)
        if status == 200 and isinstance(body, dict):
            last = str(body.get("status") or "")
            if last and last != "WAITING_APPROVAL":
                return last
        time.sleep(0.5)
    return last


def wait_terminal(base: str, token: str, org_id: str, run_id: str, timeout: int) -> str:
    deadline = time.monotonic() + timeout
    last = ""
    terminals = {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}
    while time.monotonic() < deadline:
        status, body = rm13.public_get(base, token, org_id, f"/api/v1/runs/{run_id}", timeout)
        if status == 200 and isinstance(body, dict):
            last = str(body.get("status") or "").upper()
            if last in terminals:
                return last
        time.sleep(0.5)
    return last


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
    print("RM-17 live env complete")
    return 0


# @lat: [[architecture/skill-agent#RM-17 Public Approval Decision]]
def run_live() -> dict[str, Any]:
    backend = rm13.require_named("RM13_BACKEND_BASE_URL", "RM12_BACKEND_BASE_URL")
    user_jwt = rm13.require_named("RM13_USER_JWT", "RM12_USER_JWT")
    org_id = rm13.require_named("RM13_ORG_ID", "RM12_ORG_ID")
    preferred_tool = os.environ.get("RM15_TOOL_NAME") or rm13.require_named("RM13_TOOL_NAME", "RM12_TOOL_NAME")
    agent_base = rm13.require_named("RM13_AGENT_BASE_URL", "RM12_AGENT_BASE_URL")
    agent_token = rm13.require_named("SKILL_AGENT_INTERNAL_TOKEN")
    hermes_base = rm13.require_named("RM13_HERMES_BASE_URL")
    hermes_key = rm13.require_named("RM13_HERMES_API_SERVER_KEY")
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
    tool_name, _requires = rm15.select_live_tool(tools, preferred_tool)

    deny_run = rm15.start_bound_run(
        backend=backend,
        user_jwt=user_jwt,
        org_id=org_id,
        tool_name=tool_name,
        agent_base=agent_base,
        agent_token=agent_token,
        timeout=timeout,
        idempotency_prefix="rm17-deny",
    )
    waited = rm15.wait_for_waiting_approval(
        run_id=deny_run["run_id"],
        timeout=timeout,
        backend=backend,
        user_jwt=user_jwt,
        org_id=org_id,
        hermes_base=hermes_base,
        hermes_key=hermes_key,
        runtime_run_id=str(deny_run.get("runtime_run_id") or ""),
    )
    if not waited.get("observed") or not waited.get("approval_id"):
        raise LiveBlocked(BLOCKER, "no WAITING_APPROVAL / approval.requested for deny run")
    frames = read_sse_frames(backend, user_jwt, org_id, deny_run["run_id"], timeout)
    requested = next((item for item in frames if item.get("event_type") == "approval.requested"), None)
    if requested is None:
        raise LiveBlocked(BLOCKER, "public SSE missing approval.requested")
    payload = requested.get("payload") if isinstance(requested.get("payload"), dict) else {}
    if payload.get("options") != ["allow", "deny"]:
        raise LiveBlocked(BLOCKER, "approval.requested options are not allow/deny")
    leaks = rm13.scan_public_surface(requested) + rm13.scan_public_surface(waited.get("items") or [])
    if leaks:
        raise LiveBlocked(BLOCKER, "public surface leak")

    deny_key = f"rm17-deny-{uuid.uuid4()}"
    deny_status, deny_body = public_decision(
        backend,
        user_jwt,
        org_id,
        deny_run["run_id"],
        str(waited["approval_id"]),
        {"decision": "deny"},
        deny_key,
        timeout,
    )
    if deny_status != 200 or not isinstance(deny_body, dict):
        raise LiveBlocked(BLOCKER, f"deny decision HTTP {deny_status}")
    if "code" in deny_body or "data" in deny_body:
        raise LiveBlocked(BLOCKER, "deny receipt used Portal envelope")
    if deny_body.get("decision") != "deny":
        raise LiveBlocked(BLOCKER, "deny receipt decision mismatch")
    replay_status, replay_body = public_decision(
        backend,
        user_jwt,
        org_id,
        deny_run["run_id"],
        str(waited["approval_id"]),
        {"decision": "deny"},
        deny_key,
        timeout,
    )
    if replay_status != 200 or replay_body != deny_body:
        raise LiveBlocked(BLOCKER, "idempotent replay failed")
    conflict_status, conflict_body = public_decision(
        backend,
        user_jwt,
        org_id,
        deny_run["run_id"],
        str(waited["approval_id"]),
        {"decision": "allow"},
        deny_key,
        timeout,
    )
    if conflict_status != 409 or not isinstance(conflict_body, dict) or conflict_body.get("error_code") != "IDEMPOTENCY_CONFLICT":
        raise LiveBlocked(BLOCKER, f"conflict expected 409 IDEMPOTENCY_CONFLICT got {conflict_status}")
    decided_status, decided_body = public_decision(
        backend,
        user_jwt,
        org_id,
        deny_run["run_id"],
        str(waited["approval_id"]),
        {"decision": "deny"},
        f"rm17-deny-new-{uuid.uuid4()}",
        timeout,
    )
    if decided_status != 409 or not isinstance(decided_body, dict) or decided_body.get("error_code") != "APPROVAL_ALREADY_DECIDED":
        raise LiveBlocked(BLOCKER, f"already decided expected 409 got {decided_status}")
    other_org = f"org-rm17-{uuid.uuid4()}"
    cross_status, _cross_body = public_decision(
        backend,
        user_jwt,
        other_org,
        deny_run["run_id"],
        str(waited["approval_id"]),
        {"decision": "deny"},
        f"rm17-cross-{uuid.uuid4()}",
        timeout,
    )
    if cross_status not in {401, 403, 404}:
        raise LiveBlocked(BLOCKER, f"cross-tenant expected fail-closed got {cross_status}")
    deny_terminal = wait_terminal(backend, user_jwt, org_id, deny_run["run_id"], timeout)
    if deny_terminal != "FAILED":
        raise LiveBlocked(BLOCKER, f"deny Public terminal observed {deny_terminal or 'none'}; expected FAILED")

    allow_run = rm15.start_bound_run(
        backend=backend,
        user_jwt=user_jwt,
        org_id=org_id,
        tool_name=tool_name,
        agent_base=agent_base,
        agent_token=agent_token,
        timeout=timeout,
        idempotency_prefix="rm17-allow",
    )
    allow_waited = rm15.wait_for_waiting_approval(
        run_id=allow_run["run_id"],
        timeout=timeout,
        backend=backend,
        user_jwt=user_jwt,
        org_id=org_id,
        hermes_base=hermes_base,
        hermes_key=hermes_key,
        runtime_run_id=str(allow_run.get("runtime_run_id") or ""),
    )
    if not allow_waited.get("observed") or not allow_waited.get("approval_id"):
        raise LiveBlocked(BLOCKER, "no WAITING_APPROVAL for allow run")
    allow_status, allow_body = public_decision(
        backend,
        user_jwt,
        org_id,
        allow_run["run_id"],
        str(allow_waited["approval_id"]),
        {"decision": "allow"},
        f"rm17-allow-{uuid.uuid4()}",
        timeout,
    )
    if allow_status != 200 or not isinstance(allow_body, dict) or allow_body.get("decision") != "allow":
        raise LiveBlocked(BLOCKER, f"allow decision HTTP {allow_status}")
    if "code" in allow_body or "data" in allow_body:
        raise LiveBlocked(BLOCKER, "allow receipt used Portal envelope")
    left = wait_status_leave_waiting(backend, user_jwt, org_id, allow_run["run_id"], timeout)
    if left == "WAITING_APPROVAL" or not left:
        raise LiveBlocked(BLOCKER, "allow did not leave WAITING_APPROVAL")

    get_status, get_body = rm13.public_get(backend, user_jwt, org_id, f"/api/v1/runs/{allow_run['run_id']}", timeout)
    if get_status != 200:
        raise LiveBlocked(BLOCKER, f"GET run HTTP {get_status}")
    leaks.extend(rm13.scan_public_surface(allow_body))
    leaks.extend(rm13.scan_public_surface(deny_body))
    leaks.extend(rm13.scan_public_surface(get_body))
    if leaks:
        raise LiveBlocked(BLOCKER, "public surface leak after decision")

    return {
        "schema": "smc.rm17.live-v130.v1",
        "policy": "REAL_PROCESS",
        "result": "PASS",
        "auth_type": "user_jwt",
        "deny_terminal": deny_terminal,
        "allow_left_waiting": left,
        "timestamp": rm13.utcnow(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-env", action="store_true")
    parser.add_argument("--probe-candidate", action="store_true")
    args = parser.parse_args()
    if args.preflight_env:
        return preflight_env()
    if args.probe_candidate:
        return probe_candidate()
    claims = fail_claims("not-run")
    try:
        evidence = run_live()
    except (LiveBlocked, rm13.LiveBlocked) as exc:
        code = getattr(exc, "code", BLOCKER)
        print(f"{code}: {exc}", file=sys.stderr)
        emit_result(claims)
        return 1
    if evidence.get("result") != "PASS":
        emit_result(claims)
        return 1
    emit_result({cid: "PASS" for cid in CLAIMS})
    print("RM-17 live public approval PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

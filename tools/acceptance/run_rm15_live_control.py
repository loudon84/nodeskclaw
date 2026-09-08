#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_rm13_live_native as rm13
import run_rm14_live_semantic as rm14

BLOCKER = "RM15_LIVE_V13_BLOCKED"


def public_post(
    base: str,
    token: str,
    org_id: str,
    path: str,
    body: dict[str, Any],
    timeout: int,
) -> tuple[int, Any]:
    status, raw = rm13._http(
        "POST",
        f"{base.rstrip('/')}{path}",
        headers={"Authorization": f"Bearer {token}", "X-Org-Id": org_id},
        body=body,
        timeout=timeout,
    )
    return status, rm13.unwrap_data(rm13._json_body(raw))


def catalog_requires_approval(item: dict[str, Any]) -> bool:
    if item.get("requiresApproval"):
        return True
    annotations = item.get("annotations") if isinstance(item.get("annotations"), dict) else {}
    return bool(annotations.get("requiresApproval"))


def select_live_tool(tools: list[Any], preferred: str) -> tuple[str, bool]:
    override = (os.environ.get("RM15_TOOL_NAME") or "").strip()
    chosen = override or preferred
    selected = next(
        (item for item in tools if isinstance(item, dict) and item.get("name") == chosen),
        None,
    )
    requires = catalog_requires_approval(selected) if isinstance(selected, dict) else False
    return chosen, requires


def approval_id_from_sot(items: list[dict[str, Any]]) -> str | None:
    found = None
    for item in items:
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        if item.get("event_type") == "approval.requested":
            value = str(payload.get("approval_id") or "").strip()
            if value:
                found = value
    return found


def waiting_from_sot(items: list[dict[str, Any]]) -> bool:
    if approval_id_from_sot(items):
        return True
    for item in items:
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        if item.get("event_type") == "run.progress" and str(payload.get("phase") or "").upper() == "WAITING_APPROVAL":
            return True
    return False


def approval_id_from_runtime(body: Any, runtime_run_id: str) -> str | None:
    if not isinstance(body, dict):
        return None
    nested = body.get("data") if isinstance(body.get("data"), dict) else {}
    approval = body.get("approval") if isinstance(body.get("approval"), dict) else {}
    nested_approval = nested.get("approval") if isinstance(nested.get("approval"), dict) else {}
    candidates = [
        body.get("approval_id"),
        nested.get("approval_id"),
        approval.get("approval_id"),
        nested_approval.get("approval_id"),
        approval.get("id"),
        nested_approval.get("id"),
    ]
    for item in candidates:
        if isinstance(item, str) and item.strip() and item.strip() != runtime_run_id:
            return item.strip()
    return None


def wait_for_waiting_approval(
    *,
    run_id: str,
    timeout: int,
    backend: str,
    user_jwt: str,
    org_id: str,
    hermes_base: str,
    hermes_key: str,
    runtime_run_id: str,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: list[dict[str, Any]] = []
    public_status = None
    hermes_status = None
    approval_id = None
    observed = False
    while time.monotonic() < deadline:
        last = rm14.query_sot_events(run_id)
        approval_id = approval_id_from_sot(last) or approval_id
        if waiting_from_sot(last):
            observed = True
        get_status, get_body = rm13.public_get(backend, user_jwt, org_id, f"/api/v1/runs/{run_id}", timeout)
        if get_status == 200 and isinstance(get_body, dict):
            public_status = get_body.get("status")
            if str(public_status or "").upper() == "WAITING_APPROVAL":
                observed = True
        hermes_http, hermes_body = rm13.hermes_get_run(hermes_base, hermes_key, runtime_run_id, timeout)
        if hermes_http == 200:
            nested = hermes_body.get("data") if isinstance(hermes_body, dict) and isinstance(hermes_body.get("data"), dict) else {}
            hermes_status = None
            if isinstance(hermes_body, dict):
                hermes_status = hermes_body.get("status") or nested.get("status")
            if str(hermes_status or "").strip().lower() in {"waiting_for_approval", "waiting"}:
                observed = True
            approval_id = approval_id or approval_id_from_runtime(hermes_body, runtime_run_id)
        if observed and approval_id:
            return {
                "approval_id": approval_id,
                "items": last,
                "observed": True,
                "public_status": public_status,
                "hermes_status": hermes_status,
            }
        hermes_terminal = str(hermes_status or "").strip().lower() in {
            "completed",
            "succeeded",
            "success",
            "failed",
            "error",
            "cancelled",
            "canceled",
            "interrupted",
        }
        public_terminal = str(public_status or "").upper() in {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}
        if (hermes_terminal or public_terminal) and not observed:
            break
        time.sleep(0.5)
    return {
        "approval_id": approval_id,
        "items": last,
        "observed": observed,
        "public_status": public_status,
        "hermes_status": hermes_status,
    }


def start_bound_run(
    *,
    backend: str,
    user_jwt: str,
    org_id: str,
    tool_name: str,
    agent_base: str,
    agent_token: str,
    timeout: int,
    idempotency_prefix: str,
) -> dict[str, Any]:
    call_status, call_payload = rm13.mcp_call(
        backend,
        user_jwt,
        org_id,
        "tools/call",
        {"name": tool_name, "arguments": rm13.tool_arguments()},
        timeout=timeout,
        idempotency_key=f"{idempotency_prefix}-{uuid.uuid4()}",
    )
    if call_status != 200:
        raise rm13.LiveBlocked(BLOCKER, f"tools/call HTTP {call_status}")
    envelope = rm13.envelope_from_mcp(call_payload)
    run_id = str(envelope.get("run_id") or "")
    if not run_id:
        raise rm13.LiveBlocked(BLOCKER, "tools/call missing run_id")
    leak_paths = rm13.scan_public_surface(call_payload)
    rm13.wait_until_agent_has_run(agent_base, agent_token, org_id, run_id, timeout)
    binding = rm13.wait_for_binding(run_id, timeout)
    runtime_run_id = str(binding.get("runtime_run_id") or "")
    if not runtime_run_id:
        raise rm13.LiveBlocked(BLOCKER, "attempt runtime binding missing runtime_run_id")
    return {
        "run_id": run_id,
        "attempt_id": binding.get("attempt_id"),
        "generation": binding.get("generation"),
        "runtime_run_id": runtime_run_id,
        "runtime_run_id_hash": rm13.sha256_text(runtime_run_id),
        "public_leaks": leak_paths,
        "envelope": envelope,
    }


def sot_event_types(items: list[dict[str, Any]]) -> list[str]:
    types: list[str] = []
    for item in items:
        event_type = str(item.get("event_type") or "")
        if event_type and event_type not in types:
            types.append(event_type)
    return types


# @lat: [[architecture/skill-agent#RM-15 Live Control V13]]
def run_live() -> dict[str, Any]:
    backend = rm13.require_named("RM13_BACKEND_BASE_URL", "RM12_BACKEND_BASE_URL")
    user_jwt = rm13.require_named("RM13_USER_JWT", "RM12_USER_JWT")
    org_id = rm13.require_named("RM13_ORG_ID", "RM12_ORG_ID")
    preferred_tool = rm13.require_named("RM13_TOOL_NAME", "RM12_TOOL_NAME")
    agent_base = rm13.require_named("RM13_AGENT_BASE_URL", "RM12_AGENT_BASE_URL")
    agent_token = rm13.require_named("SKILL_AGENT_INTERNAL_TOKEN")
    hermes_base = rm13.require_named("RM13_HERMES_BASE_URL")
    hermes_key = rm13.require_named("RM13_HERMES_API_SERVER_KEY")
    rm13.require_named("RM13_AGENT_DATABASE_URL")
    timeout = rm13.timeout_seconds()
    secrets = (user_jwt, agent_token, hermes_key)

    evidence: dict[str, Any] = {
        "schema": "smc.rm15.live-v13.v1",
        "policy": "REAL_PROCESS",
        "result": "FAIL",
        "timestamp": rm13.utcnow(),
        "session_rejected": False,
        "deny_http_not_500": False,
        "approve_http_not_500": False,
        "waiting_approval_observed": False,
        "public_runtime_identity_leak": False,
        "public_leaks": [],
        "native_paths_observed": [],
        "chat_completions_observed": False,
    }

    health_status, _ = rm13._http("GET", f"{backend.rstrip('/')}/api/v1/health", headers={}, timeout=timeout)
    if health_status != 200:
        raise rm13.LiveBlocked(BLOCKER, f"backend health HTTP {health_status}")

    caps = rm13.probe_hermes(hermes_base, hermes_key, timeout)
    evidence["hermes_runtime_version"] = caps["hermes_runtime_version"]
    evidence["observed_version"] = caps.get("observed_version")
    evidence["version_source"] = caps.get("version_source")
    evidence["native_paths_observed"].append("/v1/capabilities")

    list_status, list_payload = rm13.mcp_call(backend, user_jwt, org_id, "tools/list", {}, timeout=timeout)
    if list_status != 200:
        raise rm13.LiveBlocked(BLOCKER, f"tools/list HTTP {list_status}")
    tools = ((list_payload.get("result") or {}) if isinstance(list_payload.get("result"), dict) else {}).get("tools")
    if not isinstance(tools, list):
        raise rm13.LiveBlocked(BLOCKER, "tools/list missing tools")
    tool_name, tool_requires_approval = select_live_tool(tools, preferred_tool)
    if not any(isinstance(item, dict) and item.get("name") == tool_name for item in tools):
        raise rm13.LiveBlocked(BLOCKER, f"tool not in catalog: {tool_name}")
    evidence["tool_name"] = tool_name
    evidence["tool_requires_approval"] = tool_requires_approval

    wait_run = start_bound_run(
        backend=backend,
        user_jwt=user_jwt,
        org_id=org_id,
        tool_name=tool_name,
        agent_base=agent_base,
        agent_token=agent_token,
        timeout=timeout,
        idempotency_prefix="rm15-wait",
    )
    evidence["run_id"] = wait_run["run_id"]
    evidence["attempt_id"] = wait_run["attempt_id"]
    evidence["generation"] = wait_run["generation"]
    evidence["runtime_run_id_hash"] = wait_run["runtime_run_id_hash"]
    evidence["public_leaks"].extend(wait_run["public_leaks"])
    evidence["native_paths_observed"].extend(["/v1/runs", "/v1/runs/<id>/events", "/v1/runs/<id>"])

    waited = wait_for_waiting_approval(
        run_id=wait_run["run_id"],
        timeout=timeout,
        backend=backend,
        user_jwt=user_jwt,
        org_id=org_id,
        hermes_base=hermes_base,
        hermes_key=hermes_key,
        runtime_run_id=wait_run["runtime_run_id"],
    )
    sot_items = waited["items"]
    approval_id = waited["approval_id"]
    evidence["waiting_approval_observed"] = bool(waited["observed"])
    evidence["public_run_status"] = waited["public_status"]
    evidence["hermes_run_status"] = waited["hermes_status"]
    evidence["observed_event_types"] = sot_event_types(sot_items)
    if not evidence["waiting_approval_observed"] or not approval_id:
        cancel_status, cancel_body = public_post(
            backend,
            user_jwt,
            org_id,
            f"/api/v1/runs/{wait_run['run_id']}/cancel",
            {},
            timeout,
        )
        evidence["cancel_http"] = cancel_status
        evidence["cancel_run_id"] = wait_run["run_id"]
        evidence["public_leaks"].extend(f"cancel:{item}" for item in rm13.scan_public_surface(cancel_body))
        evidence["public_runtime_identity_leak"] = bool(evidence["public_leaks"])
        evidence["result"] = "BLOCKED"
        evidence["blocker"] = BLOCKER
        evidence["message"] = (
            f"no WAITING_APPROVAL / approval.requested; live Native did not emit approval for tool={tool_name} "
            f"run_id={wait_run['run_id']} hermes_runtime_version={evidence.get('hermes_runtime_version')} "
            f"public_status={waited['public_status']} hermes_status={waited['hermes_status']} "
            f"event_types={evidence['observed_event_types']}"
        )
        return rm13.redact(evidence, secrets)
    evidence["approval_id"] = approval_id

    session_status, _ = public_post(
        backend,
        user_jwt,
        org_id,
        f"/api/v1/runs/{wait_run['run_id']}/approvals/{approval_id}",
        {"decision": "session"},
        timeout,
    )
    evidence["session_http"] = session_status
    evidence["session_rejected"] = session_status in {400, 403, 409, 422}
    if session_status >= 500:
        raise rm13.LiveBlocked(BLOCKER, f"session approval HTTP {session_status}")

    deny_status, deny_body = public_post(
        backend,
        user_jwt,
        org_id,
        f"/api/v1/runs/{wait_run['run_id']}/approvals/{approval_id}",
        {"decision": "deny"},
        timeout,
    )
    evidence["deny_http"] = deny_status
    evidence["deny_http_not_500"] = deny_status < 500
    if deny_status >= 500:
        raise rm13.LiveBlocked(BLOCKER, f"deny approval HTTP {deny_status}")
    evidence["public_leaks"].extend(f"deny:{item}" for item in rm13.scan_public_surface(deny_body))

    approve_run = start_bound_run(
        backend=backend,
        user_jwt=user_jwt,
        org_id=org_id,
        tool_name=tool_name,
        agent_base=agent_base,
        agent_token=agent_token,
        timeout=timeout,
        idempotency_prefix="rm15-approve",
    )
    evidence["approve_run_id"] = approve_run["run_id"]
    approve_waited = wait_for_waiting_approval(
        run_id=approve_run["run_id"],
        timeout=timeout,
        backend=backend,
        user_jwt=user_jwt,
        org_id=org_id,
        hermes_base=hermes_base,
        hermes_key=hermes_key,
        runtime_run_id=approve_run["runtime_run_id"],
    )
    approve_id = approve_waited["approval_id"]
    if not approve_id:
        raise rm13.LiveBlocked(BLOCKER, f"approve path missing approval_id run_id={approve_run['run_id']}")
    approve_status, approve_body = public_post(
        backend,
        user_jwt,
        org_id,
        f"/api/v1/runs/{approve_run['run_id']}/approvals/{approve_id}",
        {"decision": "approve"},
        timeout,
    )
    evidence["approve_http"] = approve_status
    evidence["approve_http_not_500"] = approve_status < 500
    if approve_status >= 500:
        raise rm13.LiveBlocked(BLOCKER, f"approve HTTP {approve_status}")
    evidence["public_leaks"].extend(f"approve:{item}" for item in rm13.scan_public_surface(approve_body))

    cancel_run = start_bound_run(
        backend=backend,
        user_jwt=user_jwt,
        org_id=org_id,
        tool_name=tool_name,
        agent_base=agent_base,
        agent_token=agent_token,
        timeout=timeout,
        idempotency_prefix="rm15-cancel",
    )
    evidence["cancel_run_id"] = cancel_run["run_id"]
    cancel_status, cancel_body = public_post(
        backend,
        user_jwt,
        org_id,
        f"/api/v1/runs/{cancel_run['run_id']}/cancel",
        {},
        timeout,
    )
    evidence["cancel_http"] = cancel_status
    evidence["public_leaks"].extend(f"cancel:{item}" for item in rm13.scan_public_surface(cancel_body))
    evidence["native_paths_observed"].append("/v1/runs/<id>/stop")

    get_status, get_body = rm13.public_get(
        backend, user_jwt, org_id, f"/api/v1/runs/{cancel_run['run_id']}", timeout
    )
    if get_status == 200 and isinstance(get_body, dict):
        evidence["cancel_public_status"] = get_body.get("status")
        evidence["public_leaks"].extend(f"get_run:{item}" for item in rm13.scan_public_surface(get_body))
    evidence["public_runtime_identity_leak"] = bool(evidence["public_leaks"])

    version_ok = str(evidence.get("hermes_runtime_version") or "").startswith("v2026.8.31") or (
        str(evidence.get("hermes_runtime_version") or "") >= "v2026.8.31"
    )
    all_pass = (
        version_ok
        and evidence["session_rejected"]
        and evidence["deny_http_not_500"]
        and evidence["approve_http_not_500"]
        and evidence["waiting_approval_observed"]
        and not evidence["public_runtime_identity_leak"]
        and not evidence["chat_completions_observed"]
    )
    evidence["result"] = "PASS" if all_pass else "FAIL"
    if not all_pass:
        evidence["blocker"] = BLOCKER
    return rm13.redact(evidence, secrets)


def main() -> int:
    raw = [part.strip("`") for part in sys.argv[1:]]
    output = "docs_agent/evidence/RM-15-live-v13.json"
    if "--output" in raw:
        index = raw.index("--output")
        if index + 1 < len(raw):
            output = raw[index + 1]
    if "--self-check" in raw:
        return rm13.self_check()
    preflight = any(part.startswith("--preflight-env") for part in raw)
    chained_live = "then" in raw or any(part.endswith("run_rm15_live_control.py") for part in raw[1:])
    if preflight:
        missing = rm13.missing_live_vars()
        if missing:
            print("REAL_HERMES_RUNTIME_UNAVAILABLE")
            for name in missing:
                print(f"missing: {name}")
            return 2
        print("RM-15 live env complete")
        if not chained_live:
            return 0
    output_path = Path(output)
    try:
        evidence = run_live()
    except rm13.LiveBlocked as exc:
        payload = {
            "schema": "smc.rm15.live-v13.v1",
            "policy": "REAL_PROCESS",
            "result": "BLOCKED",
            "blocker": exc.code,
            "message": str(exc),
            "timestamp": rm13.utcnow(),
        }
        rm13.write_output(output_path, payload)
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 1
    rm13.write_output(output_path, evidence)
    if evidence.get("result") != "PASS":
        print(str(evidence.get("blocker") or BLOCKER), file=sys.stderr)
        if evidence.get("message"):
            print(str(evidence["message"]), file=sys.stderr)
        return 1
    print("RM-15 live V13 PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_rm12_live_conformance as rm12
import run_rm13_live_native as rm13
import run_rm14_live_semantic as rm14
import run_rm15_live_control as rm15

BLOCKER = "RM16_LIVE_CONFORMANCE_BLOCKED"
PARK_TOOL = "hermes_marketing__park-waiting-approval"
PUBLIC_TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}
SOT_TERMINAL = {"run.completed", "run.failed", "run.cancelled", "run.timed_out"}
SCENARIOS = (
    "pc01",
    "pc02",
    "pc03-approve",
    "pc03-deny",
    "pc04",
    "pc05",
    "pc06",
    "pc07",
    "pc08",
    "pc09",
    "pc12-scan",
    "rm02-package",
)
LONG_CHINESE_PROMPT = (
    "请用中文写一份不少于五百字的市场分析报告，覆盖产品定位、渠道、风险与下一步。"
    "不要调用工具，不要请求审批，不要输出推理摘要，只输出完整正文。"
)
PLAIN_PROMPT = "只用纯中文完整回答：介绍 DeskClaw 团队版是什么。不要调用工具，不要请求审批。"

ATTEMPT_QUERY = r"""
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
        SELECT id, generation, status, runtime_run_id
        FROM "{schema}".run_attempts
        WHERE run_id = :run_id
        ORDER BY generation ASC
        '''
    )
    async with engine.connect() as conn:
        rows = (await conn.execute(sql, {"run_id": run_id})).mappings().all()
    await engine.dispose()
    items = []
    for row in rows:
        items.append(
            {
                "id": str(row["id"]),
                "generation": int(row["generation"] or 0),
                "status": row["status"],
                "has_runtime_run_id": bool(row["runtime_run_id"]),
            }
        )
    print(json.dumps({"count": len(items), "items": items}, default=str))


asyncio.run(main())
"""

EXPIRE_LEASE_QUERY = r"""
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
        UPDATE "{schema}".runs
        SET lease_until = NOW() - INTERVAL '1 second', updated_at = NOW()
        WHERE id = :run_id
        RETURNING id
        '''
    )
    async with engine.begin() as conn:
        row = (await conn.execute(sql, {"run_id": run_id})).first()
    await engine.dispose()
    print(json.dumps({"updated": row is not None}))


asyncio.run(main())
"""


def fail(message: str, code: str = BLOCKER) -> None:
    raise rm13.LiveBlocked(code, message)


def no_proxy_has_lan() -> bool:
    value = ",".join(
        [
            os.environ.get("no_proxy", ""),
            os.environ.get("NO_PROXY", ""),
        ]
    )
    return "192.168.0.0/16" in value


def reject_mock_event_source() -> None:
    haystack = " ".join(
        [
            os.environ.get("RM16_EVENT_SOURCE", ""),
            os.environ.get("OPENAI_BASE_URL", ""),
            os.environ.get("RM13_HERMES_BASE_URL", ""),
            os.environ.get("RM16_ALLOW_MOCK", ""),
        ]
    ).lower()
    if "chat/completions" in haystack or "mock-openai" in haystack or os.environ.get("RM16_ALLOW_MOCK") == "1":
        fail("mock-only ChatCompletion Event Source cannot close RM-16", "RM16_MOCK_ONLY")


def park_tool_name() -> str:
    chosen = (os.environ.get("RM15_TOOL_NAME") or "").strip()
    if chosen != PARK_TOOL:
        fail(f"RM15_TOOL_NAME must be explicitly {PARK_TOOL}")
    return chosen


@dataclass
class BoundRuntimeContext:
    hermes_agent_instance_id: str
    agent_profile: str | None
    api_server_base_url: str
    api_server_key: str
    runtime_version: str | None
    runtime_run_id: str | None


HERMES_RUNNING_STATUSES = frozenset({"running", "alive"})
HERMES_WAIT_STATUSES = frozenset({"waiting_for_approval", "waiting"})
HERMES_TERMINAL_STATUSES = frozenset(
    {"completed", "failed", "cancelled", "canceled", "interrupted", "stopped", "timed_out"}
)
PC07_PUBLIC_FORBIDDEN = (
    "subagent.",
    "child_session_id",
    "runtime_run_id",
    "runtime_session_id",
    "internal.runtime.trace",
)


def missing_rm16_preflight_vars() -> list[str]:
    required = [
        ("RM13_BACKEND_BASE_URL", "RM12_BACKEND_BASE_URL"),
        ("RM13_USER_JWT", "RM12_USER_JWT"),
        ("RM13_ORG_ID", "RM12_ORG_ID"),
        ("RM13_AGENT_BASE_URL", "RM12_AGENT_BASE_URL"),
        ("SKILL_AGENT_INTERNAL_TOKEN",),
        ("RM13_AGENT_DATABASE_URL",),
    ]
    missing: list[str] = []
    for names in required:
        if not rm13.env_first(*names):
            missing.append(" or ".join(names))
    return missing


def env_ctx() -> dict[str, Any]:
    reject_mock_event_source()
    backend = rm13.require_named("RM13_BACKEND_BASE_URL", "RM12_BACKEND_BASE_URL")
    user_jwt = rm13.require_named("RM13_USER_JWT", "RM12_USER_JWT")
    org_id = rm13.require_named("RM13_ORG_ID", "RM12_ORG_ID")
    agent_base = rm13.require_named("RM13_AGENT_BASE_URL", "RM12_AGENT_BASE_URL")
    agent_token = rm13.require_named("SKILL_AGENT_INTERNAL_TOKEN")
    rm13.require_named("RM13_AGENT_DATABASE_URL")
    return {
        "backend": backend,
        "user_jwt": user_jwt,
        "org_id": org_id,
        "agent_base": agent_base,
        "agent_token": agent_token,
        "timeout": rm13.timeout_seconds(),
        "secrets": (user_jwt, agent_token),
    }


def base_evidence(scenario: str) -> dict[str, Any]:
    return {
        "schema": "smc.rm16.live-conformance.v1",
        "policy": "REAL_PROCESS",
        "result": "FAIL",
        "scenario": scenario,
        "auth_type": "user_jwt",
        "timestamp": rm13.utcnow(),
        "reused_runners": [
            "tools/acceptance/run_rm12_live_conformance.py",
            "tools/acceptance/run_rm13_live_native.py",
            "tools/acceptance/run_rm14_live_semantic.py",
            "tools/acceptance/run_rm15_live_control.py",
        ],
        "chat_completions_observed": False,
        "native_paths_observed": [],
        "public_leaks": [],
        "public_runtime_identity_leak": False,
        "runtime_binding_verified": False,
    }


def probe_and_health(ctx: dict[str, Any], evidence: dict[str, Any]) -> None:
    if not no_proxy_has_lan():
        fail("no_proxy/NO_PROXY must include 192.168.0.0/16")
    health_status, _ = rm13._http("GET", f"{ctx['backend'].rstrip('/')}/api/v1/health", headers={}, timeout=ctx["timeout"])
    if health_status != 200:
        fail(f"backend health HTTP {health_status}")
    evidence["backend_health"] = health_status


def finish(evidence: dict[str, Any], secrets: tuple[str, ...], ok: bool, message: str | None = None) -> dict[str, Any]:
    evidence["public_runtime_identity_leak"] = bool(evidence.get("public_leaks"))
    evidence["result"] = "PASS" if ok and not evidence["public_runtime_identity_leak"] and not evidence["chat_completions_observed"] else "FAIL"
    if message:
        evidence["message"] = message
    if evidence["result"] != "PASS":
        evidence["blocker"] = evidence.get("blocker") or BLOCKER
    return rm13.redact(evidence, secrets)


def catalog_tool_names(ctx: dict[str, Any]) -> set[str]:
    list_status, list_payload = rm13.mcp_call(
        ctx["backend"],
        ctx["user_jwt"],
        ctx["org_id"],
        "tools/list",
        {},
        timeout=ctx["timeout"],
    )
    if list_status != 200:
        fail(f"tools/list HTTP {list_status}")
    result = list_payload.get("result") if isinstance(list_payload, dict) else None
    tools = result.get("tools") if isinstance(result, dict) else None
    if not isinstance(tools, list):
        fail("tools/list missing result.tools")
    names: set[str] = set()
    for item in tools:
        if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"]:
            names.add(item["name"])
    return names


def require_catalog_tool(ctx: dict[str, Any], tool_name: str, blocker: str) -> None:
    if tool_name not in catalog_tool_names(ctx):
        fail(f"catalog missing tool {tool_name}", blocker)


def expected_instance_id(env_name: str | None) -> str | None:
    if not env_name:
        return None
    value = (os.environ.get(env_name) or "").strip()
    return value or None


def agent_get_run(ctx: dict[str, Any], run_id: str) -> dict[str, Any]:
    status, raw = rm13._http(
        "GET",
        f"{ctx['agent_base'].rstrip('/')}/internal/v1/runs/{run_id}",
        headers={"X-Skill-Agent-Token": ctx["agent_token"], "X-Exec-Org-Id": ctx["org_id"]},
        timeout=ctx["timeout"],
    )
    if status != 200:
        fail(f"agent GET run HTTP {status}", "RM16_RUNTIME_BINDING_MISSING")
    body = rm13._json_body(raw)
    payload = rm13.unwrap_data(body) if isinstance(body, dict) else body
    if not isinstance(payload, dict):
        fail("agent GET run returned non-object", "RM16_RUNTIME_BINDING_MISSING")
    return payload


def credential_lease_ref_from_snapshot(snapshot: Any) -> dict[str, Any] | None:
    if not isinstance(snapshot, dict):
        return None
    policy = snapshot.get("runtime_policy")
    if isinstance(policy, dict) and isinstance(policy.get("credential_lease_ref"), dict):
        return policy["credential_lease_ref"]
    if isinstance(snapshot.get("credential_lease_ref"), dict):
        return snapshot["credential_lease_ref"]
    return None


def wait_for_attempt(run_id: str, timeout: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {"found": False}
    while time.monotonic() < deadline:
        last = rm13.query_binding(run_id)
        if last.get("found") and last.get("attempt_id"):
            return last
        time.sleep(0.5)
    fail("attempt row missing for run", "RM16_RUNTIME_BINDING_MISSING")
    raise AssertionError("unreachable")


def bound_url_port(url: str) -> int:
    parsed = urlparse(url)
    if parsed.port is not None:
        return int(parsed.port)
    if parsed.scheme == "https":
        return 443
    return 80


def probe_bound_capabilities(bound_url: str, api_key: str, timeout: int) -> dict[str, Any]:
    try:
        status, raw = rm13._http(
            "GET",
            f"{bound_url.rstrip('/')}/v1/capabilities",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
    except rm13.LiveBlocked as exc:
        fail(str(exc), "RM16_BOUND_RUNTIME_PROBE_FAILED")
        raise AssertionError("unreachable") from exc
    if status != 200:
        fail(f"bound capabilities HTTP {status}", "RM16_BOUND_RUNTIME_PROBE_FAILED")
    body = rm13._json_body(raw)
    if not isinstance(body, dict):
        fail("bound capabilities is not JSON object", "RM16_BOUND_RUNTIME_PROBE_FAILED")
    version_raw = str(body.get("version") or body.get("hermes_version") or body.get("runtime_version") or "")
    version_source = "capabilities"
    if not version_raw:
        health_status, health_raw = rm13._http(
            "GET",
            f"{bound_url.rstrip('/')}/health",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        if health_status != 200:
            fail(f"bound /health HTTP {health_status}", "RM16_BOUND_RUNTIME_PROBE_FAILED")
        health_body = rm13._json_body(health_raw)
        if not isinstance(health_body, dict):
            fail("bound /health is not JSON object", "RM16_BOUND_RUNTIME_PROBE_FAILED")
        version_raw = str(health_body.get("version") or "")
        version_source = "health"
    return {"version": version_raw, "version_source": version_source, "body": body}


def mint_bound_credentials(
    ctx: dict[str, Any],
    *,
    run_id: str,
    attempt_id: str,
    lease_ref: dict[str, Any],
) -> dict[str, Any]:
    status, raw = rm13._http(
        "POST",
        f"{ctx['backend'].rstrip('/')}/api/v1/internal/v1/skill-agent/credentials/mint",
        headers={
            "X-Skill-Agent-Token": ctx["agent_token"],
            "X-Exec-Org-Id": ctx["org_id"],
        },
        body={
            "run_id": run_id,
            "attempt_id": attempt_id,
            "instance_id": lease_ref.get("instance_id"),
            "agent_profile": lease_ref.get("agent_profile"),
            "scope": lease_ref.get("scope") or "hermes:invoke",
            "target": lease_ref.get("target"),
        },
        timeout=ctx["timeout"],
    )
    if status != 200:
        fail(f"credential mint HTTP {status}", "RM16_CREDENTIAL_LEASE_FAILED")
    payload = rm13._json_body(raw)
    minted = rm13.unwrap_data(payload) if isinstance(payload, dict) else payload
    if not isinstance(minted, dict):
        fail("credential mint returned non-object", "RM16_CREDENTIAL_LEASE_FAILED")
    return minted


# @lat: [[architecture/skill-agent#RM-16 Live Conformance]]
def resolve_bound_runtime(
    ctx: dict[str, Any],
    *,
    run_id: str,
    attempt_id: str | None,
    runtime_run_id: str | None,
    expected_env: str | None = None,
) -> BoundRuntimeContext:
    run_view = agent_get_run(ctx, run_id)
    snapshot = run_view.get("snapshot")
    lease_ref = credential_lease_ref_from_snapshot(snapshot)
    if not isinstance(lease_ref, dict):
        fail("run snapshot missing credential_lease_ref", "RM16_RUNTIME_BINDING_MISSING")
    instance_id = str(lease_ref.get("instance_id") or "").strip()
    if not instance_id:
        fail("credential_lease_ref missing instance_id", "RM16_RUNTIME_INSTANCE_MISSING")
    expected = expected_instance_id(expected_env)
    if expected and expected != instance_id:
        fail(
            f"bound instance {instance_id} != expected {expected}",
            "RM16_BOUND_RUNTIME_INSTANCE_MISMATCH",
        )
    resolved_attempt = str(attempt_id or run_view.get("attempt_id") or "").strip()
    if not resolved_attempt:
        fail("attempt_id missing for credential mint", "RM16_RUNTIME_BINDING_MISSING")
    minted = mint_bound_credentials(
        ctx,
        run_id=run_id,
        attempt_id=resolved_attempt,
        lease_ref=lease_ref,
    )
    gateway_url = str(minted.get("gateway_url") or "").rstrip("/")
    token = str(minted.get("token") or minted.get("api_server_key") or "")
    if not gateway_url:
        fail("credential mint missing gateway_url", "RM16_BOUND_RUNTIME_URL_MISSING")
    if not token:
        fail("credential mint missing token", "RM16_CREDENTIAL_LEASE_FAILED")
    caps = probe_bound_capabilities(gateway_url, token, ctx["timeout"])
    profile = lease_ref.get("agent_profile")
    return BoundRuntimeContext(
        hermes_agent_instance_id=instance_id,
        agent_profile=str(profile) if isinstance(profile, str) and profile else None,
        api_server_base_url=gateway_url,
        api_server_key=token,
        runtime_version=caps.get("version") or None,
        runtime_run_id=runtime_run_id or None,
    )


def apply_bound_evidence(evidence: dict[str, Any], bound: BoundRuntimeContext) -> None:
    evidence["runtime_binding_verified"] = True
    evidence["hermes_agent_instance_id"] = bound.hermes_agent_instance_id
    evidence["agent_profile"] = bound.agent_profile
    evidence["bound_api_server_url_hash"] = rm13.sha256_text(bound.api_server_base_url)
    evidence["bound_api_server_port"] = bound_url_port(bound.api_server_base_url)
    if bound.runtime_version:
        evidence["hermes_runtime_version"] = bound.runtime_version
        evidence["observed_version"] = bound.runtime_version
    if bound.runtime_run_id:
        evidence["runtime_run_id_hash"] = rm13.sha256_text(bound.runtime_run_id)
    evidence["native_paths_observed"].append("/v1/capabilities")


def merge_secrets(ctx: dict[str, Any], bound: BoundRuntimeContext) -> tuple[str, ...]:
    secrets = list(ctx["secrets"])
    if bound.api_server_key:
        secrets.append(bound.api_server_key)
    return tuple(secrets)


def attach_started(evidence: dict[str, Any], started: dict[str, Any]) -> None:
    evidence.update(
        {
            "run_id": started["run_id"],
            "attempt_id": started["attempt_id"],
            "generation": started["generation"],
            "public_leaks": started["public_leaks"],
        }
    )
    if started.get("runtime_run_id"):
        evidence["runtime_run_id_hash"] = started["runtime_run_id_hash"]
    apply_bound_evidence(evidence, started["bound"])
    evidence["native_paths_observed"].extend(["/v1/runs", "/v1/runs/<id>/events", "/v1/runs/<id>"])


def start_bound_run(
    ctx: dict[str, Any],
    *,
    tool_name: str,
    arguments: dict[str, Any],
    prefix: str,
    require_runtime_run_id: bool = True,
    expected_env: str | None = "RM16_EXPECTED_PRIMARY_INSTANCE_ID",
) -> dict[str, Any]:
    call_status, call_payload = rm13.mcp_call(
        ctx["backend"],
        ctx["user_jwt"],
        ctx["org_id"],
        "tools/call",
        {"name": tool_name, "arguments": arguments},
        timeout=ctx["timeout"],
        idempotency_key=f"{prefix}-{uuid.uuid4()}",
    )
    if call_status != 200:
        fail(f"tools/call HTTP {call_status}")
    envelope = rm13.envelope_from_mcp(call_payload)
    run_id = str(envelope.get("run_id") or "")
    if not run_id:
        fail("tools/call missing run_id")
    leaks = rm13.scan_public_surface(call_payload)
    leaks.extend(rm12.scan_public_surface(call_payload))
    dumped_call = json.dumps(call_payload, ensure_ascii=False)
    if "/v1/chat/completions" in dumped_call:
        fail("ChatCompletion fallback observed on tools/call", "RM16_MOCK_ONLY")
    rm13.wait_until_agent_has_run(ctx["agent_base"], ctx["agent_token"], ctx["org_id"], run_id, ctx["timeout"])
    if require_runtime_run_id:
        binding = rm13.wait_for_binding(run_id, ctx["timeout"])
        runtime_run_id = str(binding.get("runtime_run_id") or "")
        if not runtime_run_id:
            fail("attempt runtime binding missing runtime_run_id", "RM16_RUNTIME_BINDING_MISSING")
    else:
        binding = wait_for_attempt(run_id, ctx["timeout"])
        runtime_run_id = str(binding.get("runtime_run_id") or "") or None
    attempt_id = str(binding.get("attempt_id") or "")
    bound = resolve_bound_runtime(
        ctx,
        run_id=run_id,
        attempt_id=attempt_id,
        runtime_run_id=runtime_run_id,
        expected_env=expected_env,
    )
    return {
        "run_id": run_id,
        "attempt_id": attempt_id or binding.get("attempt_id"),
        "generation": binding.get("generation"),
        "runtime_run_id": runtime_run_id,
        "runtime_run_id_hash": rm13.sha256_text(runtime_run_id) if runtime_run_id else None,
        "public_leaks": leaks,
        "envelope": envelope,
        "bound": bound,
        "secrets": merge_secrets(ctx, bound),
    }


def start_stable_running_run(
    ctx: dict[str, Any],
    evidence: dict[str, Any],
    *,
    prefix: str,
    expected_env: str = "RM16_EXPECTED_RUNNING_INSTANCE_ID",
) -> dict[str, Any]:
    tool_name = (os.environ.get("RM16_RUNNING_TOOL_NAME") or "").strip()
    if not tool_name:
        fail("missing RM16_RUNNING_TOOL_NAME", "RM16_RUNNING_FIXTURE_UNSTABLE")
    if tool_name == PARK_TOOL:
        fail("PC-05/PC-08 must not use park-waiting-approval", "RM16_RUNNING_FIXTURE_UNSTABLE")
    require_catalog_tool(ctx, tool_name, "RM16_RUNNING_FIXTURE_UNSTABLE")
    hold = int(os.environ.get("RM16_RUNNING_MIN_HOLD_SECONDS") or "3")
    prompt = (os.environ.get("RM16_RUNNING_PROMPT") or "").strip() or (
        "请持续执行当前任务，完成前保持运行，不要请求审批，不要立即结束。"
    )
    started = start_bound_run(
        ctx,
        tool_name=tool_name,
        arguments={"prompt": prompt},
        prefix=prefix,
        expected_env=expected_env,
    )
    evidence["tool_name"] = tool_name
    attach_started(evidence, started)
    runtime_run_id = str(started.get("runtime_run_id") or "")
    if not runtime_run_id:
        fail("stable running fixture missing runtime_run_id", "RM16_RUNNING_FIXTURE_UNSTABLE")
    stable_since: float | None = None
    last_public = None
    last_hermes = ""
    deadline = time.monotonic() + ctx["timeout"]
    while time.monotonic() < deadline:
        get_status, body = rm13.public_get(
            ctx["backend"], ctx["user_jwt"], ctx["org_id"], f"/api/v1/runs/{started['run_id']}", ctx["timeout"]
        )
        if get_status == 200 and isinstance(body, dict):
            last_public = str(body.get("status") or "").upper()
        last_hermes = hermes_status(started["bound"], runtime_run_id, ctx["timeout"])
        if last_public == "WAITING_APPROVAL" or last_hermes in HERMES_WAIT_STATUSES:
            fail("running fixture entered waiting_for_approval", "RM16_RUNNING_FIXTURE_UNSTABLE")
        if last_public in PUBLIC_TERMINAL or last_hermes in HERMES_TERMINAL_STATUSES:
            fail("running fixture terminated before fault injection", "RM16_RUNNING_FIXTURE_UNSTABLE")
        if last_public == "RUNNING" and last_hermes in HERMES_RUNNING_STATUSES:
            if stable_since is None:
                stable_since = time.monotonic()
            elif time.monotonic() - stable_since >= hold:
                evidence["fault_fixture"] = "stable_running"
                evidence["pre_fault_public_status"] = last_public
                evidence["pre_fault_hermes_status"] = last_hermes
                evidence["pre_fault_runtime_binding_verified"] = True
                return started
        else:
            stable_since = None
        time.sleep(0.5)
    fail("stable RUNNING window not observed", "RM16_RUNNING_FIXTURE_UNSTABLE")
    raise AssertionError("unreachable")


def tool_arguments(default_prompt: str) -> dict[str, Any]:
    raw = rm13.env_first("RM16_TOOL_ARGUMENTS", "RM13_TOOL_ARGUMENTS", "RM12_TOOL_ARGUMENTS")
    if raw:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            fail("tool arguments must be JSON object")
        return parsed
    return {"prompt": default_prompt}


def wait_terminal(ctx: dict[str, Any], run_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + ctx["timeout"]
    last_status = None
    last_items: list[dict[str, Any]] = []
    last_body: Any = None
    while time.monotonic() < deadline:
        last_items = rm14.query_sot_events(run_id)
        types = {str(item.get("event_type") or "") for item in last_items}
        get_status, last_body = rm13.public_get(
            ctx["backend"], ctx["user_jwt"], ctx["org_id"], f"/api/v1/runs/{run_id}", ctx["timeout"]
        )
        if get_status == 200 and isinstance(last_body, dict):
            last_status = str(last_body.get("status") or "").upper()
        if (types & SOT_TERMINAL) or (last_status in PUBLIC_TERMINAL):
            return {"status": last_status, "items": last_items, "body": last_body}
        time.sleep(0.5)
    return {"status": last_status, "items": last_items, "body": last_body}


def public_sse(ctx: dict[str, Any], run_id: str) -> list[dict[str, Any]]:
    try:
        events, _eof = rm12.read_sse(
            ctx["backend"], ctx["user_jwt"], ctx["org_id"], run_id, min(ctx["timeout"], 90)
        )
        return events
    except rm12.LiveBlocked:
        return []


def assistant_texts(items: list[dict[str, Any]]) -> list[str]:
    texts: list[str] = []
    for item in items:
        if item.get("event_type") != "assistant.message":
            continue
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else item
        text = ""
        if isinstance(payload, dict):
            text = str(payload.get("text") or payload.get("content") or "")
        if text:
            texts.append(text)
    return texts


def tool_calls(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for item in items:
        if item.get("event_type") != "tool.call":
            continue
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        found.append(payload if isinstance(payload, dict) else {})
    return found


def query_attempts(run_id: str) -> dict[str, Any]:
    env = os.environ.copy()
    completed = subprocess.run(
        ["uv", "--directory", "nodeskclaw-agent", "run", "python", "-c", ATTEMPT_QUERY, run_id],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        fail(f"attempt query failed: {(completed.stderr or completed.stdout or '')[-400:]}")
    line = (completed.stdout or "").strip().splitlines()[-1] if (completed.stdout or "").strip() else ""
    parsed = json.loads(line)
    if not isinstance(parsed, dict):
        fail("attempt query returned non-object")
    return parsed


def expire_run_lease(run_id: str) -> None:
    env = os.environ.copy()
    completed = subprocess.run(
        ["uv", "--directory", "nodeskclaw-agent", "run", "python", "-c", EXPIRE_LEASE_QUERY, run_id],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        fail(f"lease expire failed: {(completed.stderr or completed.stdout or '')[-400:]}")


def gap_from_sot(items: list[dict[str, Any]]) -> bool:
    for item in items:
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        if payload.get("kind") == "worker_restart_gap" or payload.get("observability_gap") is True:
            return True
        dumped = json.dumps(payload, ensure_ascii=False)
        if "worker_restart_gap" in dumped or '"observability_gap": true' in dumped.lower():
            return True
    return False


def scan_surfaces(ctx: dict[str, Any], run_id: str, evidence: dict[str, Any], extra: Any = None) -> None:
    leaks = list(evidence.get("public_leaks") or [])
    surfaces: list[tuple[str, Any]] = []
    if extra is not None:
        surfaces.append(("extra", extra))
        leaks.extend(rm13.scan_public_surface(extra))
        leaks.extend(rm12.scan_public_surface(extra))
    for label, path in (
        ("get_run", f"/api/v1/runs/{run_id}"),
        ("get_result", f"/api/v1/runs/{run_id}/result"),
        ("get_artifacts", f"/api/v1/runs/{run_id}/artifacts"),
    ):
        status, body = rm13.public_get(ctx["backend"], ctx["user_jwt"], ctx["org_id"], path, ctx["timeout"])
        if status == 200:
            surfaces.append((label, body))
            leaks.extend(f"{label}:{item}" for item in rm13.scan_public_surface(body))
            leaks.extend(f"{label}:{item}" for item in rm12.scan_public_surface(body))
            dumped = json.dumps(body, ensure_ascii=False)
            if "/api/v1/hermes/tasks/" in dumped:
                leaks.append(f"{label}:hermes_tasks_path")
    for label, payload in surfaces:
        dumped = json.dumps(payload, ensure_ascii=False)
        for fragment in PC07_PUBLIC_FORBIDDEN:
            if fragment in dumped:
                leaks.append(f"{label}:{fragment}")
    evidence["public_leaks"] = sorted(set(leaks))


def hermes_status(bound: BoundRuntimeContext, runtime_run_id: str, timeout: int) -> str:
    http_status, body = rm13.hermes_get_run(
        bound.api_server_base_url,
        bound.api_server_key,
        runtime_run_id,
        timeout,
    )
    if http_status != 200 or not isinstance(body, dict):
        return ""
    nested = body.get("data") if isinstance(body.get("data"), dict) else {}
    return str(body.get("status") or nested.get("status") or "").strip().lower()


def wait_hermes_left_waiting(bound: BoundRuntimeContext, runtime_run_id: str, timeout: int) -> str:
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        last = hermes_status(bound, runtime_run_id, timeout)
        if last and last not in HERMES_WAIT_STATUSES:
            return last
        time.sleep(0.5)
    return last


def run_pc01(ctx: dict[str, Any]) -> dict[str, Any]:
    evidence = base_evidence("pc01")
    probe_and_health(ctx, evidence)
    tool_name = rm13.env_first("RM16_PLAIN_TOOL_NAME", "RM13_TOOL_NAME", "RM12_TOOL_NAME")
    if not tool_name:
        fail("missing RM16_PLAIN_TOOL_NAME or RM13_TOOL_NAME")
    started = start_bound_run(
        ctx,
        tool_name=tool_name,
        arguments=tool_arguments(os.environ.get("RM16_PLAIN_PROMPT") or PLAIN_PROMPT),
        prefix="rm16-pc01",
    )
    evidence["tool_name"] = tool_name
    attach_started(evidence, started)
    waited = wait_terminal(ctx, started["run_id"])
    sse_events = public_sse(ctx, started["run_id"])
    sot = rm14.evaluate_sot(waited["items"])
    texts = assistant_texts(waited["items"]) or assistant_texts(sse_events)
    joined = "".join(texts)
    fake_tool = any(item.get("event_type") == "tool.call" for item in waited["items"])
    fake_approval = any(item.get("event_type") == "approval.requested" for item in waited["items"])
    tokenish = sum(1 for item in waited["items"] if item.get("event_type") in {"run.progress", "assistant.delta"})
    assistant_count = max(sot.get("assistant_message_count") or 0, len(texts))
    coalesced = assistant_count > 0 and (tokenish == 0 or assistant_count < max(tokenish, 8))
    scan_surfaces(ctx, started["run_id"], evidence, sse_events)
    ok = (
        bool(evidence.get("runtime_binding_verified"))
        and bool(joined.strip())
        and coalesced
        and not fake_tool
        and not fake_approval
        and sot.get("reasoning_summary_count", 0) == 0
        and (waited["status"] in PUBLIC_TERMINAL or bool(joined.strip()))
    )
    evidence["sot"] = sot
    evidence["assistant_message_count"] = assistant_count
    evidence["public_text_chars"] = len(joined)
    evidence["public_status"] = waited["status"]
    return finish(evidence, started["secrets"], ok, None if ok else "PC-01 plain text quality failed")


def run_pc02(ctx: dict[str, Any]) -> dict[str, Any]:
    evidence = base_evidence("pc02")
    probe_and_health(ctx, evidence)
    tool_name = rm13.env_first("RM16_TOOL_NAME", "RM13_TOOL_NAME", "RM12_TOOL_NAME")
    if not tool_name:
        fail("missing RM16_TOOL_NAME or RM13_TOOL_NAME")
    started = start_bound_run(
        ctx,
        tool_name=tool_name,
        arguments=tool_arguments("请实际调用一个工具完成任务，然后给出结果。"),
        prefix="rm16-pc02",
    )
    evidence["tool_name"] = tool_name
    attach_started(evidence, started)
    waited = wait_terminal(ctx, started["run_id"])
    sse_events = public_sse(ctx, started["run_id"])
    calls = tool_calls(waited["items"]) or tool_calls(sse_events)
    ids = [str(item.get("call_id") or "") for item in calls if item.get("call_id")]
    statuses = {str(item.get("status") or "").lower() for item in calls}
    ok = bool(calls) and bool(ids) and len(set(ids)) == 1 and bool(statuses & {"started", "running"}) and bool(
        statuses & {"completed", "failed", "succeeded", "success"}
    )
    if not ok and calls:
        by_id: dict[str, set[str]] = {}
        for item in calls:
            call_id = str(item.get("call_id") or "")
            by_id.setdefault(call_id, set()).add(str(item.get("status") or "").lower())
        ok = any(
            call_id and (values & {"started", "running"}) and (values & {"completed", "failed", "succeeded", "success"})
            for call_id, values in by_id.items()
        )
    scan_surfaces(ctx, started["run_id"], evidence, sse_events)
    evidence["tool_call_count"] = len(calls)
    evidence["tool_call_ids"] = sorted(set(ids))
    evidence["sse_event_types"] = [str(item.get("event_type") or "") for item in sse_events]
    evidence["public_status"] = waited["status"]
    ok = bool(ok) and bool(evidence.get("runtime_binding_verified"))
    return finish(evidence, started["secrets"], ok, None if ok else "PC-02 missing public tool.call with shared call_id")


def _approval_round(
    ctx: dict[str, Any],
    *,
    scenario: str,
    decision: str,
) -> dict[str, Any]:
    evidence = base_evidence(scenario)
    probe_and_health(ctx, evidence)
    tool_name = park_tool_name()
    started = start_bound_run(
        ctx,
        tool_name=tool_name,
        arguments=rm13.tool_arguments(),
        prefix=f"rm16-{scenario}",
    )
    evidence["tool_name"] = tool_name
    attach_started(evidence, started)
    bound: BoundRuntimeContext = started["bound"]
    waited = rm15.wait_for_waiting_approval(
        run_id=started["run_id"],
        timeout=ctx["timeout"],
        backend=ctx["backend"],
        user_jwt=ctx["user_jwt"],
        org_id=ctx["org_id"],
        hermes_base=bound.api_server_base_url,
        hermes_key=bound.api_server_key,
        runtime_run_id=started["runtime_run_id"],
    )
    approval_id = waited.get("approval_id")
    evidence["waiting_approval_observed"] = bool(waited.get("observed"))
    evidence["approval_id"] = approval_id
    evidence["hermes_run_status_before"] = waited.get("hermes_status")
    if not evidence["waiting_approval_observed"] or not approval_id:
        fail("no WAITING_APPROVAL / approval.requested for park tool")
    session_status, _ = rm15.public_post(
        ctx["backend"],
        ctx["user_jwt"],
        ctx["org_id"],
        f"/api/v1/runs/{started['run_id']}/approvals/{approval_id}",
        {"decision": "session"},
        ctx["timeout"],
    )
    always_status, _ = rm15.public_post(
        ctx["backend"],
        ctx["user_jwt"],
        ctx["org_id"],
        f"/api/v1/runs/{started['run_id']}/approvals/{approval_id}",
        {"decision": "always"},
        ctx["timeout"],
    )
    evidence["session_http"] = session_status
    evidence["always_http"] = always_status
    evidence["session_rejected"] = session_status in {400, 403, 409, 422}
    evidence["always_rejected"] = always_status in {400, 403, 409, 422}
    decision_status, decision_body = rm15.public_post(
        ctx["backend"],
        ctx["user_jwt"],
        ctx["org_id"],
        f"/api/v1/runs/{started['run_id']}/approvals/{approval_id}",
        {"decision": decision},
        ctx["timeout"],
    )
    evidence[f"{decision}_http"] = decision_status
    evidence["http_not_500"] = decision_status < 500
    if extra := rm13.scan_public_surface(decision_body):
        evidence["public_leaks"].extend(f"{decision}:{item}" for item in extra)
    if decision_status >= 500:
        fail(f"{decision} HTTP {decision_status}")
    if decision_status >= 400:
        fail(f"{decision} HTTP {decision_status}; HTTP non-500 is not PC-03 exit")
    after = wait_hermes_left_waiting(bound, started["runtime_run_id"], ctx["timeout"])
    evidence["hermes_run_status_after"] = after
    accepted = bool(after) and after not in HERMES_WAIT_STATUSES
    if accepted:
        evidence["native_paths_observed"].append("/v1/runs/<id>/approval")
    evidence["approval_accepted"] = accepted
    get_status, get_body = rm13.public_get(
        ctx["backend"], ctx["user_jwt"], ctx["org_id"], f"/api/v1/runs/{started['run_id']}", ctx["timeout"]
    )
    public_status = str((get_body or {}).get("status") or "").upper() if get_status == 200 else None
    evidence["public_status"] = public_status
    scan_surfaces(ctx, started["run_id"], evidence, decision_body)
    ok = (
        bool(evidence.get("runtime_binding_verified"))
        and accepted
        and evidence["session_rejected"]
        and evidence["always_rejected"]
        and "/v1/runs/<id>/approval" in evidence["native_paths_observed"]
    )
    return finish(evidence, started["secrets"], ok, None if ok else f"Hermes did not accept /approval for {decision}")


def run_pc03_approve(ctx: dict[str, Any]) -> dict[str, Any]:
    return _approval_round(ctx, scenario="pc03-approve", decision="approve")


def run_pc03_deny(ctx: dict[str, Any]) -> dict[str, Any]:
    return _approval_round(ctx, scenario="pc03-deny", decision="deny")


def run_pc04(ctx: dict[str, Any]) -> dict[str, Any]:
    evidence = base_evidence("pc04")
    probe_and_health(ctx, evidence)
    tool_name = park_tool_name()
    started = start_bound_run(
        ctx,
        tool_name=tool_name,
        arguments=rm13.tool_arguments(),
        prefix="rm16-pc04",
    )
    evidence["tool_name"] = tool_name
    attach_started(evidence, started)
    cancel_status, cancel_body = rm15.public_post(
        ctx["backend"],
        ctx["user_jwt"],
        ctx["org_id"],
        f"/api/v1/runs/{started['run_id']}/cancel",
        {},
        ctx["timeout"],
    )
    evidence["cancel_http"] = cancel_status
    if extra := rm13.scan_public_surface(cancel_body):
        evidence["public_leaks"].extend(f"cancel:{item}" for item in extra)
    if cancel_status >= 500:
        fail(f"cancel HTTP {cancel_status}")
    evidence["native_paths_observed"].append("/v1/runs/<id>/stop")
    waited = wait_terminal(ctx, started["run_id"])
    evidence["cancel_public_status"] = waited["status"]
    evidence["sot_event_types"] = [str(item.get("event_type") or "") for item in waited["items"]]
    terminal_event = any(item.get("event_type") in SOT_TERMINAL for item in waited["items"])
    stuck = waited["status"] == "CANCELLING"
    scan_surfaces(ctx, started["run_id"], evidence, cancel_body)
    ok = (
        bool(evidence.get("runtime_binding_verified"))
        and cancel_status < 500
        and not stuck
        and waited["status"] in PUBLIC_TERMINAL
        and terminal_event
    )
    return finish(
        evidence,
        started["secrets"],
        ok,
        None if ok else "PC-04 did not reach contract terminal after /stop",
    )


def run_pc05(ctx: dict[str, Any]) -> dict[str, Any]:
    evidence = base_evidence("pc05")
    probe_and_health(ctx, evidence)
    kill_cmd = (os.environ.get("RM16_WORKER_KILL_CMD") or "").strip()
    if not kill_cmd:
        fail("PC-05 requires RM16_WORKER_KILL_CMD to kill/restart the Agent Worker", "RM16_WORKER_KILL_UNAVAILABLE")
    started = start_stable_running_run(ctx, evidence, prefix="rm16-pc05")
    bound: BoundRuntimeContext = started["bound"]
    before = query_attempts(started["run_id"])
    expire_run_lease(started["run_id"])
    completed = subprocess.run(kill_cmd, shell=True, capture_output=True, text=True, check=False)
    evidence["worker_kill_exit"] = completed.returncode
    if completed.returncode != 0:
        fail(f"RM16_WORKER_KILL_CMD failed: {(completed.stderr or completed.stdout or '')[-400:]}")
    deadline = time.monotonic() + ctx["timeout"]
    items: list[dict[str, Any]] = []
    gap = False
    while time.monotonic() < deadline:
        items = rm14.query_sot_events(started["run_id"])
        gap = gap_from_sot(items)
        if gap:
            break
        time.sleep(0.5)
    after = query_attempts(started["run_id"])
    waited = wait_terminal(ctx, started["run_id"])
    terminals = [item.get("event_type") for item in waited["items"] if item.get("event_type") in SOT_TERMINAL]
    hermes_after = hermes_status(bound, started["runtime_run_id"], ctx["timeout"])
    recovered = resolve_bound_runtime(
        ctx,
        run_id=started["run_id"],
        attempt_id=started["attempt_id"],
        runtime_run_id=started["runtime_run_id"],
        expected_env="RM16_EXPECTED_RUNNING_INSTANCE_ID",
    )
    same_instance = recovered.hermes_agent_instance_id == bound.hermes_agent_instance_id
    evidence["native_paths_observed"].append("/v1/runs/<id>")
    evidence["observability_gap"] = gap
    evidence["attempt_count_before"] = before.get("count")
    evidence["attempt_count_after"] = after.get("count")
    evidence["public_terminal_events"] = terminals
    evidence["hermes_run_status_after"] = hermes_after
    evidence["public_status"] = waited["status"]
    evidence["recovered_hermes_agent_instance_id"] = recovered.hermes_agent_instance_id
    scan_surfaces(ctx, started["run_id"], evidence)
    ok = (
        bool(evidence.get("runtime_binding_verified"))
        and evidence.get("fault_fixture") == "stable_running"
        and evidence.get("pre_fault_public_status") == "RUNNING"
        and evidence.get("pre_fault_hermes_status") in HERMES_RUNNING_STATUSES
        and gap
        and same_instance
        and int(after.get("count") or 0) <= int(before.get("count") or 0) + 1
        and len(set(terminals)) <= 1
    )
    return finish(evidence, started["secrets"], ok, None if ok else "PC-05 worker restart gap/fencing failed")


def run_pc06(ctx: dict[str, Any]) -> dict[str, Any]:
    evidence = base_evidence("pc06")
    probe_and_health(ctx, evidence)
    tool_name = rm13.env_first("RM16_PLAIN_TOOL_NAME", "RM13_TOOL_NAME", "RM12_TOOL_NAME")
    if not tool_name:
        fail("missing RM16_PLAIN_TOOL_NAME or RM13_TOOL_NAME")
    started = start_bound_run(
        ctx,
        tool_name=tool_name,
        arguments={"prompt": os.environ.get("RM16_LONG_CHINESE_PROMPT") or LONG_CHINESE_PROMPT},
        prefix="rm16-pc06",
    )
    evidence["tool_name"] = tool_name
    attach_started(evidence, started)
    waited = wait_terminal(ctx, started["run_id"])
    texts = assistant_texts(waited["items"])
    joined = "".join(texts)
    tiny = [text for text in texts if 0 < len(text.strip()) <= 2]
    ok = (
        bool(evidence.get("runtime_binding_verified"))
        and len(joined) >= 80
        and len(texts) >= 1
        and len(tiny) == 0
        and joined == "".join(texts)
    )
    evidence["assistant_message_count"] = len(texts)
    evidence["public_text_chars"] = len(joined)
    evidence["tiny_fragment_count"] = len(tiny)
    evidence["public_status"] = waited["status"]
    scan_surfaces(ctx, started["run_id"], evidence)
    return finish(evidence, started["secrets"], ok, None if ok else "PC-06 long Chinese coalescing failed")


def observed_subagent_event_types(items: list[dict[str, Any]]) -> list[str]:
    observed: list[str] = []
    for item in items:
        if item.get("event_type") != "internal.runtime.trace":
            continue
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        runtime_type = str(payload.get("runtime_event_type") or "")
        if payload.get("category") == "subagent" and runtime_type.startswith("subagent."):
            observed.append(runtime_type)
    return observed


def run_pc07(ctx: dict[str, Any]) -> dict[str, Any]:
    evidence = base_evidence("pc07")
    probe_and_health(ctx, evidence)
    tool_name = (os.environ.get("RM16_SUBAGENT_TOOL_NAME") or "").strip()
    if not tool_name:
        fail("missing RM16_SUBAGENT_TOOL_NAME", "RM16_SUBAGENT_FIXTURE_UNAVAILABLE")
    require_catalog_tool(ctx, tool_name, "RM16_SUBAGENT_FIXTURE_UNAVAILABLE")
    started = start_bound_run(
        ctx,
        tool_name=tool_name,
        arguments=tool_arguments("如需委派内部子代理，请在当前 Run 内完成，不要创建外部 Child Run。"),
        prefix="rm16-pc07",
    )
    evidence["tool_name"] = tool_name
    attach_started(evidence, started)
    waited = wait_terminal(ctx, started["run_id"])
    sse_events = public_sse(ctx, started["run_id"])
    get_status, get_body = rm13.public_get(
        ctx["backend"], ctx["user_jwt"], ctx["org_id"], f"/api/v1/runs/{started['run_id']}", ctx["timeout"]
    )
    result_status, result_body = rm13.public_get(
        ctx["backend"], ctx["user_jwt"], ctx["org_id"], f"/api/v1/runs/{started['run_id']}/result", ctx["timeout"]
    )
    public_payload = {
        "sse": sse_events,
        "public": get_body if get_status == 200 else None,
        "result": result_body if result_status == 200 else None,
        "mcp": started["envelope"],
    }
    dumped = json.dumps(public_payload, ensure_ascii=False)
    child = any(fragment in dumped for fragment in PC07_PUBLIC_FORBIDDEN)
    traces = observed_subagent_event_types(waited["items"])
    scan_surfaces(ctx, started["run_id"], evidence, sse_events)
    evidence["public_status"] = waited["status"]
    evidence["internal_subagent_observed"] = bool(traces)
    evidence["observed_subagent_event_types"] = traces
    evidence["public_child_or_subagent_leak"] = child or bool(evidence.get("public_leaks"))
    if waited["status"] in PUBLIC_TERMINAL and not traces:
        return finish(
            evidence,
            started["secrets"],
            False,
            "real delegation was not observed",
        )
    ok = (
        bool(evidence.get("runtime_binding_verified"))
        and bool(traces)
        and not evidence["public_child_or_subagent_leak"]
        and waited["status"] in PUBLIC_TERMINAL
    )
    return finish(evidence, started["secrets"], ok, None if ok else "PC-07 public child/subagent leak")


def run_pc08(ctx: dict[str, Any]) -> dict[str, Any]:
    evidence = base_evidence("pc08")
    probe_and_health(ctx, evidence)
    restart_cmd = (os.environ.get("RM16_HERMES_RESTART_CMD") or "").strip()
    if not restart_cmd:
        fail("PC-08 requires RM16_HERMES_RESTART_CMD", "RM16_HERMES_RESTART_UNAVAILABLE")
    started = start_stable_running_run(ctx, evidence, prefix="rm16-pc08")
    bound: BoundRuntimeContext = started["bound"]
    expected_restart = expected_instance_id("RM16_EXPECTED_RESTART_INSTANCE_ID")
    if expected_restart and expected_restart != bound.hermes_agent_instance_id:
        fail(
            f"restart instance mismatch {bound.hermes_agent_instance_id} != {expected_restart}",
            "RM16_BOUND_RUNTIME_INSTANCE_MISMATCH",
        )
    before = query_attempts(started["run_id"])
    completed = subprocess.run(restart_cmd, shell=True, capture_output=True, text=True, check=False)
    evidence["hermes_restart_exit"] = completed.returncode
    if completed.returncode != 0:
        fail(f"RM16_HERMES_RESTART_CMD failed: {(completed.stderr or completed.stdout or '')[-400:]}")
    waited = wait_terminal(ctx, started["run_id"])
    after = query_attempts(started["run_id"])
    dumped = json.dumps(waited["items"], ensure_ascii=False)
    interrupted = "RUNTIME_INTERRUPTED" in dumped
    evidence["public_status"] = waited["status"]
    evidence["attempt_count_before"] = before.get("count")
    evidence["attempt_count_after"] = after.get("count")
    evidence["runtime_interrupted"] = interrupted
    scan_surfaces(ctx, started["run_id"], evidence)
    ok = (
        bool(evidence.get("runtime_binding_verified"))
        and evidence.get("fault_fixture") == "stable_running"
        and evidence.get("pre_fault_public_status") == "RUNNING"
        and evidence.get("pre_fault_hermes_status") in HERMES_RUNNING_STATUSES
        and waited["status"] == "FAILED"
        and interrupted
        and int(after.get("count") or 0) == int(before.get("count") or 0)
    )
    return finish(evidence, started["secrets"], ok, None if ok else "PC-08 interrupted mapping failed")


def run_pc09(ctx: dict[str, Any]) -> dict[str, Any]:
    evidence = base_evidence("pc09")
    evidence["policy"] = "REAL_PROCESS"
    probe_and_health(ctx, evidence)
    tool_name = (os.environ.get("RM16_OLD_RUNTIME_TOOL_NAME") or "").strip()
    if not tool_name:
        fail("missing RM16_OLD_RUNTIME_TOOL_NAME", "RM16_OLD_RUNTIME_UNAVAILABLE")
    require_catalog_tool(ctx, tool_name, "RM16_OLD_RUNTIME_UNAVAILABLE")
    started = start_bound_run(
        ctx,
        tool_name=tool_name,
        arguments=tool_arguments(PLAIN_PROMPT),
        prefix="rm16-pc09",
        require_runtime_run_id=False,
        expected_env="RM16_EXPECTED_OLD_INSTANCE_ID",
    )
    evidence["tool_name"] = tool_name
    attach_started(evidence, started)
    evidence["pc09_mode"] = "real_bound_old_runtime"
    bound: BoundRuntimeContext = started["bound"]
    parsed = rm13.hermes_version_for_floor(bound.runtime_version)
    below_floor = parsed is None or parsed < rm13.HERMES_VERSION_FLOOR
    evidence["old_runtime_version"] = bound.runtime_version
    evidence["version_floor_rejected"] = below_floor
    waited = wait_terminal(ctx, started["run_id"])
    dumped = json.dumps({"items": waited["items"], "body": waited["body"]}, ensure_ascii=False)
    unsupported = "RUNTIME_VERSION_UNSUPPORTED" in dumped
    chat = "/v1/chat/completions" in dumped
    evidence["chat_completions_observed"] = chat
    evidence["public_status"] = waited["status"]
    evidence["has_runtime_run_id"] = bool(started.get("runtime_run_id"))
    scan_surfaces(ctx, started["run_id"], evidence)
    ok = (
        evidence.get("pc09_mode") == "real_bound_old_runtime"
        and bool(evidence.get("runtime_binding_verified"))
        and below_floor
        and waited["status"] == "FAILED"
        and unsupported
        and not started.get("runtime_run_id")
        and not chat
    )
    return finish(evidence, started["secrets"], ok, None if ok else "PC-09 did not fail-closed on bound old runtime")


def run_pc12_scan(ctx: dict[str, Any]) -> dict[str, Any]:
    evidence = base_evidence("pc12-scan")
    probe_and_health(ctx, evidence)
    tool_name = rm13.env_first("RM16_PLAIN_TOOL_NAME", "RM13_TOOL_NAME", "RM12_TOOL_NAME")
    if not tool_name:
        fail("missing RM16_PLAIN_TOOL_NAME or RM13_TOOL_NAME")
    started = start_bound_run(
        ctx,
        tool_name=tool_name,
        arguments=tool_arguments(PLAIN_PROMPT),
        prefix="rm16-pc12",
    )
    evidence["tool_name"] = tool_name
    attach_started(evidence, started)
    wait_terminal(ctx, started["run_id"])
    sse_events = public_sse(ctx, started["run_id"])
    scan_surfaces(ctx, started["run_id"], evidence, sse_events)
    ok = bool(evidence.get("runtime_binding_verified")) and not evidence["public_leaks"]
    return finish(evidence, started["secrets"], ok, None if ok else "PC-12 public-face scan found forbidden fields")


def scenario_output_path(scenario: str) -> Path:
    slug = scenario.replace("-", "_")
    return Path(f"docs_agent/evidence/RM-16-live-{slug}.json")


def run_rm02_package() -> dict[str, Any]:
    required = [name for name in SCENARIOS if name not in {"pc12-scan", "rm02-package"}]
    missing: list[str] = []
    failed: list[str] = []
    versions: list[str] = []
    auth_types: list[str] = []
    for name in required:
        path = scenario_output_path(name)
        if not path.is_file():
            missing.append(name)
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("result") != "PASS":
            failed.append(name)
        if name == "pc09":
            if payload.get("pc09_mode") != "real_bound_old_runtime":
                failed.append("pc09:not_real_bound_old_runtime")
            if payload.get("runtime_binding_verified") is not True:
                failed.append("pc09:runtime_binding_unverified")
        if payload.get("pc09_mode") == "chat_completion_mock":
            failed.append(f"{name}:mock")
        version = str(payload.get("hermes_runtime_version") or "")
        if version:
            versions.append(version)
        auth = str(payload.get("auth_type") or "")
        if auth:
            auth_types.append(auth)
    evidence = {
        "schema": "smc.rm16.revalidation-package.v1",
        "policy": "REAL_PROCESS",
        "result": "FAIL",
        "scenario": "rm02-package",
        "auth_type": "user_jwt",
        "timestamp": rm13.utcnow(),
        "pc_scenarios": required,
        "missing": missing,
        "failed": failed,
        "hermes_runtime_versions": sorted(set(versions)),
        "auth_types": sorted(set(auth_types)),
        "revalidation_link": "RM-02 Provider Conformance",
        "note": "RM-02 Roadmap status is not rewritten by this package",
    }
    ok = not missing and not failed and "user_jwt" in set(auth_types)
    evidence["result"] = "PASS" if ok else "FAIL"
    if not ok:
        evidence["blocker"] = BLOCKER
        evidence["message"] = "RM-02 package incomplete; mock-only or missing PC evidence cannot close RM-16"
    return evidence


HANDLERS = {
    "pc01": run_pc01,
    "pc02": run_pc02,
    "pc03-approve": run_pc03_approve,
    "pc03-deny": run_pc03_deny,
    "pc04": run_pc04,
    "pc05": run_pc05,
    "pc06": run_pc06,
    "pc07": run_pc07,
    "pc08": run_pc08,
    "pc09": run_pc09,
    "pc12-scan": run_pc12_scan,
    "rm02-package": lambda _ctx: run_rm02_package(),
}


def self_check() -> int:
    if rm13.self_check() != 0:
        return 1
    if PARK_TOOL != "hermes_marketing__park-waiting-approval":
        print("self-check failed: park tool", file=sys.stderr)
        return 1
    if set(HANDLERS) != set(SCENARIOS):
        print("self-check failed: scenario handlers", file=sys.stderr)
        return 1
    leaks = rm13.scan_public_surface({"runtime_run_id": "secret", "task_id": "t1"})
    if not leaks:
        print("self-check failed: leak scan", file=sys.stderr)
        return 1
    src = Path(__file__).read_text(encoding="utf-8")
    stub_class = "class _" + "OldRuntimeStub"
    if stub_class in src:
        print("self-check failed: PC-09 stub path still present", file=sys.stderr)
        return 1
    if 'require_named("RM13_' + 'HERMES_BASE_URL")' in src:
        print("self-check failed: global Hermes URL still authoritative", file=sys.stderr)
        return 1
    if "def resolve_bound_runtime" not in src or "def start_stable_running_run" not in src:
        print("self-check failed: bound runtime helpers missing", file=sys.stderr)
        return 1
    if "park_tool_name()" in src.split("def run_pc05", 1)[-1].split("def run_pc06", 1)[0]:
        print("self-check failed: PC-05 still uses park tool", file=sys.stderr)
        return 1
    if "park_tool_name()" in src.split("def run_pc08", 1)[-1].split("def run_pc09", 1)[0]:
        print("self-check failed: PC-08 still uses park tool", file=sys.stderr)
        return 1
    print("self-check passed")
    return 0


def preflight_env() -> int:
    missing = missing_rm16_preflight_vars()
    if missing:
        print("REAL_HERMES_RUNTIME_UNAVAILABLE")
        for name in missing:
            print(f"missing: {name}")
        return 2
    if not no_proxy_has_lan():
        print("REAL_HERMES_RUNTIME_UNAVAILABLE")
        print("missing: no_proxy/NO_PROXY 192.168.0.0/16")
        return 2
    try:
        reject_mock_event_source()
        ctx = env_ctx()
        probe_and_health(ctx, base_evidence("preflight"))
        print("RM-16 live env complete")
        print("auth_type=user_jwt")
        print("runtime_route=run_bound_credential_lease")
        print("reused=run_rm12_live_conformance.py,run_rm13_live_native.py,run_rm14_live_semantic.py,run_rm15_live_control.py")
        return 0
    except rm13.LiveBlocked as exc:
        print(exc.code)
        print(str(exc))
        return 2


# @lat: [[architecture/skill-agent#RM-16 Live Conformance]]
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--output")
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--preflight-env", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        return self_check()
    if args.preflight_env:
        return preflight_env()
    if not args.scenario:
        parser.error("--scenario is required unless --self-check or --preflight-env")
    output = Path(args.output) if args.output else scenario_output_path(args.scenario)
    try:
        if args.scenario == "rm02-package":
            evidence = run_rm02_package()
        else:
            evidence = HANDLERS[args.scenario](env_ctx())
    except rm13.LiveBlocked as exc:
        payload = {
            "schema": "smc.rm16.live-conformance.v1",
            "policy": "REAL_PROCESS",
            "result": "BLOCKED",
            "scenario": args.scenario,
            "auth_type": "user_jwt",
            "blocker": exc.code,
            "message": str(exc),
            "timestamp": rm13.utcnow(),
        }
        rm13.write_output(output, payload)
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 1
    rm13.write_output(output, evidence)
    if evidence.get("result") != "PASS":
        print(str(evidence.get("blocker") or BLOCKER), file=sys.stderr)
        if evidence.get("message"):
            print(str(evidence["message"]), file=sys.stderr)
        return 1
    print(f"RM-16 {args.scenario} PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

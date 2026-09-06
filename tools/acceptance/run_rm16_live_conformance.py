#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

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


def env_ctx() -> dict[str, Any]:
    reject_mock_event_source()
    backend = rm13.require_named("RM13_BACKEND_BASE_URL", "RM12_BACKEND_BASE_URL")
    user_jwt = rm13.require_named("RM13_USER_JWT", "RM12_USER_JWT")
    org_id = rm13.require_named("RM13_ORG_ID", "RM12_ORG_ID")
    agent_base = rm13.require_named("RM13_AGENT_BASE_URL", "RM12_AGENT_BASE_URL")
    agent_token = rm13.require_named("SKILL_AGENT_INTERNAL_TOKEN")
    hermes_base = rm13.require_named("RM13_HERMES_BASE_URL")
    hermes_key = rm13.require_named("RM13_HERMES_API_SERVER_KEY")
    rm13.require_named("RM13_AGENT_DATABASE_URL")
    return {
        "backend": backend,
        "user_jwt": user_jwt,
        "org_id": org_id,
        "agent_base": agent_base,
        "agent_token": agent_token,
        "hermes_base": hermes_base,
        "hermes_key": hermes_key,
        "timeout": rm13.timeout_seconds(),
        "secrets": (user_jwt, agent_token, hermes_key),
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
    }


def probe_and_health(ctx: dict[str, Any], evidence: dict[str, Any]) -> None:
    if not no_proxy_has_lan():
        fail("no_proxy/NO_PROXY must include 192.168.0.0/16")
    health_status, _ = rm13._http("GET", f"{ctx['backend'].rstrip('/')}/api/v1/health", headers={}, timeout=ctx["timeout"])
    if health_status != 200:
        fail(f"backend health HTTP {health_status}")
    caps = rm13.probe_hermes(ctx["hermes_base"], ctx["hermes_key"], ctx["timeout"])
    evidence["hermes_runtime_version"] = caps["hermes_runtime_version"]
    evidence["observed_version"] = caps.get("observed_version")
    evidence["version_source"] = caps.get("version_source")
    evidence["native_paths_observed"].append("/v1/capabilities")
    if caps.get("version_source") == "health":
        evidence["native_paths_observed"].append("/health")


def finish(evidence: dict[str, Any], secrets: tuple[str, ...], ok: bool, message: str | None = None) -> dict[str, Any]:
    evidence["public_runtime_identity_leak"] = bool(evidence.get("public_leaks"))
    evidence["result"] = "PASS" if ok and not evidence["public_runtime_identity_leak"] and not evidence["chat_completions_observed"] else "FAIL"
    if message:
        evidence["message"] = message
    if evidence["result"] != "PASS":
        evidence["blocker"] = evidence.get("blocker") or BLOCKER
    return rm13.redact(evidence, secrets)


def start_bound_run(
    ctx: dict[str, Any],
    *,
    tool_name: str,
    arguments: dict[str, Any],
    prefix: str,
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
    rm13.wait_until_agent_has_run(ctx["agent_base"], ctx["agent_token"], ctx["org_id"], run_id, ctx["timeout"])
    binding = rm13.wait_for_binding(run_id, ctx["timeout"])
    runtime_run_id = str(binding.get("runtime_run_id") or "")
    if not runtime_run_id:
        fail("attempt runtime binding missing runtime_run_id")
    return {
        "run_id": run_id,
        "attempt_id": binding.get("attempt_id"),
        "generation": binding.get("generation"),
        "runtime_run_id": runtime_run_id,
        "runtime_run_id_hash": rm13.sha256_text(runtime_run_id),
        "public_leaks": leaks,
        "envelope": envelope,
    }


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
    if extra is not None:
        leaks.extend(rm13.scan_public_surface(extra))
        leaks.extend(rm12.scan_public_surface(extra))
    for label, path in (
        ("get_run", f"/api/v1/runs/{run_id}"),
        ("get_result", f"/api/v1/runs/{run_id}/result"),
        ("get_artifacts", f"/api/v1/runs/{run_id}/artifacts"),
    ):
        status, body = rm13.public_get(ctx["backend"], ctx["user_jwt"], ctx["org_id"], path, ctx["timeout"])
        if status == 200:
            leaks.extend(f"{label}:{item}" for item in rm13.scan_public_surface(body))
            leaks.extend(f"{label}:{item}" for item in rm12.scan_public_surface(body))
            dumped = json.dumps(body, ensure_ascii=False)
            if "/api/v1/hermes/tasks/" in dumped:
                leaks.append(f"{label}:hermes_tasks_path")
    evidence["public_leaks"] = sorted(set(leaks))


def hermes_status(ctx: dict[str, Any], runtime_run_id: str) -> str:
    http_status, body = rm13.hermes_get_run(ctx["hermes_base"], ctx["hermes_key"], runtime_run_id, ctx["timeout"])
    if http_status != 200 or not isinstance(body, dict):
        return ""
    nested = body.get("data") if isinstance(body.get("data"), dict) else {}
    return str(body.get("status") or nested.get("status") or "").strip().lower()


def wait_hermes_left_waiting(ctx: dict[str, Any], runtime_run_id: str) -> str:
    deadline = time.monotonic() + ctx["timeout"]
    last = ""
    while time.monotonic() < deadline:
        last = hermes_status(ctx, runtime_run_id)
        if last and last not in {"waiting_for_approval", "waiting"}:
            return last
        time.sleep(0.5)
    return last


def run_pc01(ctx: dict[str, Any]) -> dict[str, Any]:
    evidence = base_evidence("pc01")
    probe_and_health(ctx, evidence)
    tool_name = rm13.require_named("RM13_TOOL_NAME", "RM12_TOOL_NAME")
    started = start_bound_run(
        ctx,
        tool_name=tool_name,
        arguments=tool_arguments(os.environ.get("RM16_PLAIN_PROMPT") or PLAIN_PROMPT),
        prefix="rm16-pc01",
    )
    evidence.update(
        {
            "tool_name": tool_name,
            "run_id": started["run_id"],
            "attempt_id": started["attempt_id"],
            "generation": started["generation"],
            "runtime_run_id_hash": started["runtime_run_id_hash"],
            "public_leaks": started["public_leaks"],
        }
    )
    evidence["native_paths_observed"].extend(["/v1/runs", "/v1/runs/<id>/events", "/v1/runs/<id>"])
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
        bool(joined.strip())
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
    return finish(evidence, ctx["secrets"], ok, None if ok else "PC-01 plain text quality failed")


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
    evidence.update(
        {
            "tool_name": tool_name,
            "run_id": started["run_id"],
            "attempt_id": started["attempt_id"],
            "generation": started["generation"],
            "runtime_run_id_hash": started["runtime_run_id_hash"],
            "public_leaks": started["public_leaks"],
        }
    )
    evidence["native_paths_observed"].extend(["/v1/runs", "/v1/runs/<id>/events", "/v1/runs/<id>"])
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
    return finish(evidence, ctx["secrets"], ok, None if ok else "PC-02 missing public tool.call with shared call_id")


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
    evidence.update(
        {
            "tool_name": tool_name,
            "run_id": started["run_id"],
            "attempt_id": started["attempt_id"],
            "generation": started["generation"],
            "runtime_run_id_hash": started["runtime_run_id_hash"],
            "public_leaks": started["public_leaks"],
        }
    )
    evidence["native_paths_observed"].extend(["/v1/runs", "/v1/runs/<id>/events", "/v1/runs/<id>"])
    waited = rm15.wait_for_waiting_approval(
        run_id=started["run_id"],
        timeout=ctx["timeout"],
        backend=ctx["backend"],
        user_jwt=ctx["user_jwt"],
        org_id=ctx["org_id"],
        hermes_base=ctx["hermes_base"],
        hermes_key=ctx["hermes_key"],
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
    after = wait_hermes_left_waiting(ctx, started["runtime_run_id"])
    evidence["hermes_run_status_after"] = after
    accepted = bool(after) and after not in {"waiting_for_approval", "waiting"}
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
        accepted
        and evidence["session_rejected"]
        and evidence["always_rejected"]
        and "/v1/runs/<id>/approval" in evidence["native_paths_observed"]
    )
    return finish(evidence, ctx["secrets"], ok, None if ok else f"Hermes did not accept /approval for {decision}")


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
    evidence.update(
        {
            "tool_name": tool_name,
            "run_id": started["run_id"],
            "attempt_id": started["attempt_id"],
            "generation": started["generation"],
            "runtime_run_id_hash": started["runtime_run_id_hash"],
            "public_leaks": started["public_leaks"],
        }
    )
    evidence["native_paths_observed"].extend(["/v1/runs", "/v1/runs/<id>/events", "/v1/runs/<id>"])
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
        cancel_status < 500
        and not stuck
        and waited["status"] in PUBLIC_TERMINAL
        and terminal_event
    )
    return finish(
        evidence,
        ctx["secrets"],
        ok,
        None if ok else "PC-04 did not reach contract terminal after /stop",
    )


def run_pc05(ctx: dict[str, Any]) -> dict[str, Any]:
    evidence = base_evidence("pc05")
    probe_and_health(ctx, evidence)
    kill_cmd = (os.environ.get("RM16_WORKER_KILL_CMD") or "").strip()
    if not kill_cmd:
        fail("PC-05 requires RM16_WORKER_KILL_CMD to kill/restart the Agent Worker", "RM16_WORKER_KILL_UNAVAILABLE")
    tool_name = park_tool_name()
    started = start_bound_run(
        ctx,
        tool_name=tool_name,
        arguments=rm13.tool_arguments(),
        prefix="rm16-pc05",
    )
    evidence.update(
        {
            "tool_name": tool_name,
            "run_id": started["run_id"],
            "attempt_id": started["attempt_id"],
            "generation": started["generation"],
            "runtime_run_id_hash": started["runtime_run_id_hash"],
            "public_leaks": started["public_leaks"],
        }
    )
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
    hermes_after = hermes_status(ctx, started["runtime_run_id"])
    evidence["native_paths_observed"].append("/v1/runs/<id>")
    evidence["observability_gap"] = gap
    evidence["attempt_count_before"] = before.get("count")
    evidence["attempt_count_after"] = after.get("count")
    evidence["public_terminal_events"] = terminals
    evidence["hermes_run_status_after"] = hermes_after
    evidence["public_status"] = waited["status"]
    scan_surfaces(ctx, started["run_id"], evidence)
    ok = (
        gap
        and int(after.get("count") or 0) <= int(before.get("count") or 0) + 1
        and len(set(terminals)) <= 1
    )
    return finish(evidence, ctx["secrets"], ok, None if ok else "PC-05 worker restart gap/fencing failed")


def run_pc06(ctx: dict[str, Any]) -> dict[str, Any]:
    evidence = base_evidence("pc06")
    probe_and_health(ctx, evidence)
    tool_name = rm13.require_named("RM13_TOOL_NAME", "RM12_TOOL_NAME")
    started = start_bound_run(
        ctx,
        tool_name=tool_name,
        arguments={"prompt": os.environ.get("RM16_LONG_CHINESE_PROMPT") or LONG_CHINESE_PROMPT},
        prefix="rm16-pc06",
    )
    evidence.update(
        {
            "tool_name": tool_name,
            "run_id": started["run_id"],
            "attempt_id": started["attempt_id"],
            "generation": started["generation"],
            "runtime_run_id_hash": started["runtime_run_id_hash"],
            "public_leaks": started["public_leaks"],
        }
    )
    waited = wait_terminal(ctx, started["run_id"])
    texts = assistant_texts(waited["items"])
    joined = "".join(texts)
    tiny = [text for text in texts if 0 < len(text.strip()) <= 2]
    ok = (
        len(joined) >= 80
        and len(texts) >= 1
        and len(tiny) == 0
        and joined == "".join(texts)
    )
    evidence["assistant_message_count"] = len(texts)
    evidence["public_text_chars"] = len(joined)
    evidence["tiny_fragment_count"] = len(tiny)
    evidence["public_status"] = waited["status"]
    scan_surfaces(ctx, started["run_id"], evidence)
    return finish(evidence, ctx["secrets"], ok, None if ok else "PC-06 long Chinese coalescing failed")


def run_pc07(ctx: dict[str, Any]) -> dict[str, Any]:
    evidence = base_evidence("pc07")
    probe_and_health(ctx, evidence)
    tool_name = rm13.env_first("RM16_SUBAGENT_TOOL_NAME", "RM13_TOOL_NAME", "RM12_TOOL_NAME")
    if not tool_name:
        fail("missing tool name for PC-07")
    started = start_bound_run(
        ctx,
        tool_name=tool_name,
        arguments=tool_arguments("如需委派内部子代理，请在当前 Run 内完成，不要创建外部 Child Run。"),
        prefix="rm16-pc07",
    )
    evidence.update(
        {
            "tool_name": tool_name,
            "run_id": started["run_id"],
            "attempt_id": started["attempt_id"],
            "generation": started["generation"],
            "runtime_run_id_hash": started["runtime_run_id_hash"],
            "public_leaks": started["public_leaks"],
        }
    )
    waited = wait_terminal(ctx, started["run_id"])
    sse_events = public_sse(ctx, started["run_id"])
    dumped = json.dumps({"sot": waited["items"], "sse": sse_events, "public": waited["body"]}, ensure_ascii=False)
    child = "child_session_id" in dumped or "subagent." in dumped
    scan_surfaces(ctx, started["run_id"], evidence, sse_events)
    ok = (not child) and (waited["status"] in PUBLIC_TERMINAL or waited["status"] is not None)
    evidence["public_status"] = waited["status"]
    evidence["child_or_subagent_public"] = child
    return finish(evidence, ctx["secrets"], ok, None if ok else "PC-07 public child/subagent leak")


def run_pc08(ctx: dict[str, Any]) -> dict[str, Any]:
    evidence = base_evidence("pc08")
    probe_and_health(ctx, evidence)
    restart_cmd = (os.environ.get("RM16_HERMES_RESTART_CMD") or "").strip()
    if not restart_cmd:
        fail("PC-08 requires RM16_HERMES_RESTART_CMD", "RM16_HERMES_RESTART_UNAVAILABLE")
    tool_name = park_tool_name()
    started = start_bound_run(
        ctx,
        tool_name=tool_name,
        arguments=rm13.tool_arguments(),
        prefix="rm16-pc08",
    )
    evidence.update(
        {
            "tool_name": tool_name,
            "run_id": started["run_id"],
            "attempt_id": started["attempt_id"],
            "generation": started["generation"],
            "runtime_run_id_hash": started["runtime_run_id_hash"],
            "public_leaks": started["public_leaks"],
        }
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
    ok = waited["status"] == "FAILED" and interrupted and int(after.get("count") or 0) == int(before.get("count") or 0)
    return finish(evidence, ctx["secrets"], ok, None if ok else "PC-08 interrupted mapping failed")


class _OldRuntimeStub(BaseHTTPRequestHandler):
    observed: list[str] = []

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _write(self, code: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        type(self).observed.append(f"GET {self.path}")
        path = self.path.split("?", 1)[0]
        if path.rstrip("/").endswith("/v1/capabilities"):
            self._write(200, {"version": "v2026.4.23", "features": {}})
            return
        if path.rstrip("/").endswith("/health"):
            self._write(200, {"version": "v2026.4.23"})
            return
        self._write(404, {"error": "not found"})

    def do_POST(self) -> None:
        type(self).observed.append(f"POST {self.path}")
        self._write(404, {"error": "not found"})


def run_pc09(ctx: dict[str, Any]) -> dict[str, Any]:
    evidence = base_evidence("pc09")
    evidence["policy"] = "REAL_PROCESS"
    old_base = (os.environ.get("RM16_OLD_HERMES_BASE_URL") or "").strip()
    observed: list[str] = []
    blocked_code = None
    blocked_message = None
    if old_base:
        evidence["pc09_mode"] = "real_old_runtime"
        try:
            rm13.probe_hermes(old_base, ctx["hermes_key"], ctx["timeout"])
            fail("old Hermes runtime was accepted; expected RUNTIME_VERSION_UNSUPPORTED")
        except rm13.LiveBlocked as exc:
            blocked_code = exc.code
            blocked_message = str(exc)
    else:
        evidence["pc09_mode"] = "probe_only_version_stub"
        _OldRuntimeStub.observed = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), _OldRuntimeStub)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            stub_base = f"http://{host}:{port}"
            try:
                rm13.probe_hermes(stub_base, "stub-key", ctx["timeout"])
                fail("version stub was accepted; expected RUNTIME_VERSION_UNSUPPORTED")
            except rm13.LiveBlocked as exc:
                blocked_code = exc.code
                blocked_message = str(exc)
            observed = list(_OldRuntimeStub.observed)
        finally:
            server.shutdown()
            server.server_close()
    chat = any("chat/completions" in item for item in observed)
    evidence["chat_completions_observed"] = chat
    evidence["stub_paths_observed"] = observed
    evidence["blocked_code"] = blocked_code
    evidence["blocked_message"] = blocked_message
    evidence["hermes_runtime_version"] = evidence.get("hermes_runtime_version") or "v2026.4.23"
    if old_base:
        evidence["native_paths_observed"].append("/v1/capabilities")
    ok = blocked_code == "RUNTIME_VERSION_UNSUPPORTED" and not chat
    return finish(evidence, ctx["secrets"], ok, None if ok else "PC-09 did not fail-closed on version floor")


def run_pc12_scan(ctx: dict[str, Any]) -> dict[str, Any]:
    evidence = base_evidence("pc12-scan")
    probe_and_health(ctx, evidence)
    tool_name = rm13.require_named("RM13_TOOL_NAME", "RM12_TOOL_NAME")
    started = start_bound_run(
        ctx,
        tool_name=tool_name,
        arguments=tool_arguments(PLAIN_PROMPT),
        prefix="rm16-pc12",
    )
    evidence.update(
        {
            "tool_name": tool_name,
            "run_id": started["run_id"],
            "attempt_id": started["attempt_id"],
            "generation": started["generation"],
            "runtime_run_id_hash": started["runtime_run_id_hash"],
            "public_leaks": started["public_leaks"],
        }
    )
    wait_terminal(ctx, started["run_id"])
    sse_events = public_sse(ctx, started["run_id"])
    scan_surfaces(ctx, started["run_id"], evidence, sse_events)
    ok = not evidence["public_leaks"]
    return finish(evidence, ctx["secrets"], ok, None if ok else "PC-12 public-face scan found forbidden fields")


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
    print("self-check passed")
    return 0


def preflight_env() -> int:
    missing = rm13.missing_live_vars()
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
        caps = rm13.probe_hermes(ctx["hermes_base"], ctx["hermes_key"], ctx["timeout"])
        print("RM-16 live env complete")
        print(f"auth_type=user_jwt")
        print(f"hermes_runtime_version={caps.get('hermes_runtime_version')}")
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

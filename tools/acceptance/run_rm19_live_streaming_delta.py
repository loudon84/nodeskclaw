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

BLOCKER = "RM19_LIVE_STREAMING_DELTA_BLOCKED"
CLAIMS = ("CLM-01", "CLM-02", "CLM-03", "CLM-04", "CLM-05", "CLM-06")
CANDIDATE_PATH = ROOT / ".smc" / "runs" / "RM-19" / "verification-candidate.json"
SECRET_MARKERS = (
    "runtime_run_id",
    "gateway_token",
    "child_session_id",
    "Authorization",
    "sk-",
    "BEGIN PRIVATE KEY",
)
TERMINALS = {"run.completed", "run.failed", "run.cancelled", "run.timed_out"}


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
    print("RM-19 live env complete")
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
    last_event_id: str | None = None,
) -> list[dict[str, Any]]:
    url = f"{base.rstrip('/')}/api/v1/runs/{run_id}/events"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Org-Id": org_id,
        "Accept": "text/event-stream",
    }
    if last_event_id:
        headers["Last-Event-ID"] = last_event_id
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
                        et = str(payload.get("event_type") or "")
                        if et in TERMINALS:
                            return events
                    event_name = None
    except HTTPError as exc:
        raise LiveBlocked(BLOCKER, f"SSE HTTP {exc.code}") from exc
    except (URLError, TimeoutError) as exc:
        raise LiveBlocked(BLOCKER, f"SSE failed: {exc}") from exc
    return events


# @lat: [[architecture/skill-agent#RM-19 Public Streaming Delta]]
def run_live() -> dict[str, Any]:
    backend = rm13.require_named("RM13_BACKEND_BASE_URL", "RM12_BACKEND_BASE_URL")
    user_jwt = rm13.require_named("RM13_USER_JWT", "RM12_USER_JWT")
    org_id = rm13.require_named("RM13_ORG_ID", "RM12_ORG_ID")
    preferred_tool = os.environ.get("RM19_TOOL_NAME") or rm13.require_named(
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
    tool_names = {str(t.get("name") or "") for t in tools if isinstance(t, dict)}
    if preferred_tool not in tool_names:
        raise LiveBlocked(BLOCKER, f"preferred tool not in catalog: {preferred_tool}")

    args = rm13.tool_arguments()
    if "prompt" not in args:
        args = {
            **args,
            "prompt": "请连续输出一段中文说明，至少两句，便于观察流式增量。",
        }

    call_status, call_payload = rm13.mcp_call(
        backend,
        user_jwt,
        org_id,
        "tools/call",
        {"name": preferred_tool, "arguments": args},
        timeout=timeout,
        idempotency_key=f"rm19-delta-{uuid.uuid4()}",
    )
    if call_status != 200:
        raise LiveBlocked(BLOCKER, f"tools/call HTTP {call_status}")
    assert_no_secrets(call_payload)
    envelope = rm13.envelope_from_mcp(call_payload)
    run_id = str(envelope.get("run_id") or "")
    if not run_id:
        raise LiveBlocked(BLOCKER, "tools/call missing run_id")
    auth_type = str(envelope.get("auth_type") or "user_jwt")

    rm13.wait_until_agent_has_run(agent_base, agent_token, org_id, run_id, timeout)

    events = read_sse_until(backend, user_jwt, org_id, run_id, timeout=timeout)
    assert_no_secrets(events)
    deltas = [e for e in events if e.get("event_type") == "assistant.delta"]
    messages = [e for e in events if e.get("event_type") == "assistant.message"]
    terminals = [e for e in events if str(e.get("event_type") or "") in TERMINALS]
    if not deltas:
        raise LiveBlocked(BLOCKER, "no public assistant.delta observed before/at terminal")
    if not messages:
        raise LiveBlocked(BLOCKER, "no public assistant.message snapshot observed")
    if not terminals:
        raise LiveBlocked(BLOCKER, "no terminal event observed")

    first_delta_seq = min(int(e.get("event_seq") or 0) for e in deltas)
    term_seq = min(int(e.get("event_seq") or 0) for e in terminals)
    if first_delta_seq >= term_seq:
        raise LiveBlocked(BLOCKER, "assistant.delta only appeared at/after terminal (batch replay)")

    by_message: dict[str, list[tuple[int, str]]] = {}
    for event in deltas:
        payload = event.get("payload") or {}
        message_id = payload.get("message_id")
        delta = payload.get("delta")
        delta_seq = payload.get("delta_seq")
        if not isinstance(message_id, str) or not isinstance(delta, str) or not isinstance(delta_seq, int):
            raise LiveBlocked(BLOCKER, f"malformed delta payload: {payload}")
        if set(payload.keys()) - {"message_id", "delta_seq", "delta"}:
            raise LiveBlocked(BLOCKER, f"delta payload leaked keys: {sorted(payload)}")
        by_message.setdefault(message_id, []).append((delta_seq, delta))

    matched = False
    for event in messages:
        payload = event.get("payload") or {}
        message_id = payload.get("message_id")
        text = payload.get("text")
        if not isinstance(message_id, str) or not isinstance(text, str):
            raise LiveBlocked(BLOCKER, f"malformed snapshot payload: {payload}")
        if set(payload.keys()) - {"message_id", "text"}:
            raise LiveBlocked(BLOCKER, f"snapshot payload leaked keys: {sorted(payload)}")
        parts = sorted(by_message.get(message_id) or [], key=lambda item: item[0])
        joined = "".join(part for _, part in parts)
        if joined == text:
            matched = True
            break
    if not matched:
        raise LiveBlocked(BLOCKER, "delta concatenation does not match snapshot")

    event_ids = [str(e.get("event_id")) for e in events if e.get("event_id")]
    if len(event_ids) != len(set(event_ids)):
        raise LiveBlocked(BLOCKER, "duplicate event_id in first SSE pass")

    resume_from = event_ids[len(event_ids) // 2] if event_ids else None
    if resume_from:
        try:
            cursor_seq = int(str(resume_from).rsplit(":", 1)[-1])
        except ValueError as exc:
            raise LiveBlocked(BLOCKER, f"unparseable Last-Event-ID: {resume_from}") from exc
        resumed = read_sse_until(
            backend,
            user_jwt,
            org_id,
            run_id,
            timeout=min(30, timeout),
            last_event_id=resume_from,
        )
        assert_no_secrets(resumed)
        resumed_ids = [str(e.get("event_id")) for e in resumed if e.get("event_id")]
        if len(resumed_ids) != len(set(resumed_ids)):
            raise LiveBlocked(BLOCKER, "duplicate event_id within resumed SSE pass")
        for eid in resumed_ids:
            try:
                seq = int(str(eid).rsplit(":", 1)[-1])
            except ValueError as exc:
                raise LiveBlocked(BLOCKER, f"unparseable resumed event_id: {eid}") from exc
            if seq <= cursor_seq:
                raise LiveBlocked(
                    BLOCKER,
                    f"SSE resume replayed event_id at/before cursor: {eid} <= {resume_from}",
                )
        # Consumer dedupe: first-pass + resume may overlap after cursor; union by event_id.
        by_id = {str(e.get("event_id")): e for e in events if e.get("event_id")}
        for event in resumed:
            eid = str(event.get("event_id") or "")
            if not eid:
                continue
            prior = by_id.get(eid)
            if prior is not None and prior != event:
                # Same id must not disagree on public type/payload/seq.
                if (
                    prior.get("event_type") != event.get("event_type")
                    or prior.get("event_seq") != event.get("event_seq")
                    or prior.get("payload") != event.get("payload")
                ):
                    raise LiveBlocked(BLOCKER, f"SSE reconnect conflict for event_id {eid}")
            by_id[eid] = event
        if len(by_id) < len(set(event_ids)):
            raise LiveBlocked(BLOCKER, "SSE reconnect lost previously observed event_ids")

    claims = {cid: "PASS" for cid in CLAIMS}
    CANDIDATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATE_PATH.write_text(
        json.dumps(
            {
                "candidate_id": f"rm19-live-{run_id}",
                "run_id": run_id,
                "auth_type": auth_type,
                "tool_name": preferred_tool,
                "delta_count": len(deltas),
                "message_count": len(messages),
                "claims": claims,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "schema": "smc.rm19.live-v150.v1",
        "policy": "REAL_PROCESS",
        "result": "PASS",
        "auth_type": auth_type,
        "tool_name": preferred_tool,
        "run_id": run_id,
        "delta_count": len(deltas),
        "message_count": len(messages),
        "timestamp": rm13.utcnow(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="RM-19 live streaming delta conformance")
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
        if "missing" in str(exc).lower() or code == "REAL_HERMES_RUNTIME_UNAVAILABLE":
            emit_result(missing_claims(str(exc)))
            return 2
        emit_result(fail_claims(str(exc)))
        return 1
    if evidence.get("result") != "PASS":
        emit_result(fail_claims("evidence-not-pass"))
        return 1
    emit_result({cid: "PASS" for cid in CLAIMS})
    print("RM-19 live public streaming delta PASS")
    print("auth_type=" + str(evidence.get("auth_type") or ""))
    print("delta_count=" + str(evidence.get("delta_count") or 0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

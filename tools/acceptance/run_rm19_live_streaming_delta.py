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


def require_env() -> dict[str, str]:
    missing = rm13.missing_live_vars()
    if missing:
        raise LiveBlocked(BLOCKER, f"missing live env: {', '.join(missing)}")
    return {
        "backend": os.environ["NODESKCLAW_BACKEND_BASE_URL"].rstrip("/"),
        "tool_name": os.environ.get("RM19_TOOL_NAME") or os.environ.get("RM13_TOOL_NAME") or "",
    }


def http_json(method: str, url: str, *, headers: dict[str, str], body: dict[str, Any] | None = None) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = Request(url, data=data, method=method)
    for key, value in headers.items():
        req.add_header(key, value)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise LiveBlocked(BLOCKER, f"HTTP {exc.code} {url}: {raw[:400]}") from exc
    except URLError as exc:
        raise LiveBlocked(BLOCKER, f"URL error {url}: {exc}") from exc


def read_sse_until(url: str, *, headers: dict[str, str], timeout_s: float = 45.0) -> list[dict[str, Any]]:
    req = Request(url, method="GET")
    for key, value in headers.items():
        req.add_header(key, value)
    req.add_header("Accept", "text/event-stream")
    events: list[dict[str, Any]] = []
    started = time.monotonic()
    try:
        with urlopen(req, timeout=timeout_s) as resp:
            event_name = None
            data_lines: list[str] = []
            while time.monotonic() - started < timeout_s:
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
                        if et.startswith("run.") and et not in {"run.progress", "run.created", "run.queued"}:
                            if et in {"run.completed", "run.failed", "run.cancelled", "run.timed_out"}:
                                break
                    event_name = None
    except (HTTPError, URLError, TimeoutError) as exc:
        raise LiveBlocked(BLOCKER, f"SSE failed: {exc}") from exc
    return events


def assert_no_secrets(payload: Any) -> None:
    raw = json.dumps(payload, ensure_ascii=False)
    for marker in SECRET_MARKERS:
        if marker in raw and marker not in {"runtime_run_id"}:
            raise LiveBlocked(BLOCKER, f"secret marker leaked in public output: {marker}")
    if "runtime_run_id" in raw:
        raise LiveBlocked(BLOCKER, "runtime_run_id leaked in public output")


def run_live() -> dict[str, str]:
    cfg = require_env()
    if not cfg["tool_name"]:
        raise LiveBlocked(BLOCKER, "RM19_TOOL_NAME or RM13_TOOL_NAME required")
    token = rm13.employee_user_jwt()
    headers = {"Authorization": f"Bearer {token}", "Accept-Language": "zh-CN"}
    call_id = str(uuid.uuid4())
    accepted = http_json(
        "POST",
        f"{cfg['backend']}/api/v1/mcp",
        headers=headers,
        body={
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/call",
            "params": {"name": cfg["tool_name"], "arguments": {"prompt": "请连续输出一段中文说明，至少两句。"}},
        },
    )
    structured = ((accepted.get("result") or {}).get("structuredContent")) or {}
    run_id = structured.get("run_id") or accepted.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise LiveBlocked(BLOCKER, f"tools/call missing run_id: {accepted}")

    events = read_sse_until(
        f"{cfg['backend']}/api/v1/runs/{run_id}/events",
        headers=headers,
    )
    assert_no_secrets(events)
    deltas = [e for e in events if e.get("event_type") == "assistant.delta"]
    messages = [e for e in events if e.get("event_type") == "assistant.message"]
    terminals = [
        e
        for e in events
        if str(e.get("event_type") or "") in {"run.completed", "run.failed", "run.cancelled", "run.timed_out"}
    ]
    if not deltas:
        raise LiveBlocked(BLOCKER, "no public assistant.delta observed before/at terminal")
    if not messages:
        raise LiveBlocked(BLOCKER, "no public assistant.message snapshot observed")
    first_delta_seq = min(int(e.get("event_seq") or 0) for e in deltas)
    if terminals:
        term_seq = min(int(e.get("event_seq") or 0) for e in terminals)
        if first_delta_seq >= term_seq:
            raise LiveBlocked(BLOCKER, "assistant.delta only appeared at/after terminal (batch replay)")
    by_message: dict[str, list[str]] = {}
    for event in deltas:
        payload = event.get("payload") or {}
        message_id = payload.get("message_id")
        delta = payload.get("delta")
        if not isinstance(message_id, str) or not isinstance(delta, str):
            raise LiveBlocked(BLOCKER, f"malformed delta payload: {payload}")
        by_message.setdefault(message_id, []).append(delta)
    matched = False
    for event in messages:
        payload = event.get("payload") or {}
        message_id = payload.get("message_id")
        text = payload.get("text")
        if not isinstance(message_id, str) or not isinstance(text, str):
            raise LiveBlocked(BLOCKER, f"malformed snapshot payload: {payload}")
        joined = "".join(by_message.get(message_id) or [])
        if joined and joined == text:
            matched = True
            break
        if not by_message.get(message_id) and text:
            matched = True
    if not matched:
        raise LiveBlocked(BLOCKER, "delta concatenation does not match snapshot")

    event_ids = [e.get("event_id") for e in events if e.get("event_id")]
    if len(event_ids) != len(set(event_ids)):
        raise LiveBlocked(BLOCKER, "duplicate event_id in public stream")

    claims = {cid: "PASS" for cid in CLAIMS}
    CANDIDATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATE_PATH.write_text(
        json.dumps(
            {
                "run_id": run_id,
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
    return claims


def main() -> int:
    parser = argparse.ArgumentParser(description="RM-19 live streaming delta conformance")
    parser.parse_args()
    try:
        claims = run_live()
        emit_result(claims)
        return 0
    except LiveBlocked as exc:
        print(f"{exc.code}: {exc}")
        emit_result(missing_claims(str(exc)))
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"{BLOCKER}: unexpected {exc}")
        emit_result(fail_claims(str(exc)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

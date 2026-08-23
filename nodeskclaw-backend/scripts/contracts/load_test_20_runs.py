#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

DEFAULT_EVIDENCE = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "work-expert"
    / "v1.0.1"
    / "evidence"
    / "load-test-20-runs.json"
)

THRESHOLDS = {
    "min_terminal": 20,
    "max_accept_http_5xx": 0,
    "max_chat_failure_rate": 0.05,
}


def _env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


async def _jsonrpc_call(client: httpx.AsyncClient, url: str, headers: dict, method: str, params: dict) -> dict:
    response = await client.post(
        url,
        headers=headers,
        json={"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": method, "params": params},
    )
    return {"http_status": response.status_code, "body": response.json()}


async def _wait_terminal(client: httpx.AsyncClient, base: str, headers: dict, task_id: str, timeout_s: float) -> dict:
    deadline = time.monotonic() + timeout_s
    poll_count = 0
    last = {}
    while time.monotonic() < deadline:
        poll_count += 1
        response = await client.get(f"{base}/api/v1/hermes/tasks/{task_id}/result", headers=headers)
        last = {"http_status": response.status_code, "body": response.json() if response.headers.get("content-type", "").startswith("application/json") else {}}
        data = (last.get("body") or {}).get("data") or {}
        status = data.get("status")
        if status in {"completed", "failed", "timeout", "cancelled"}:
            return {"status": status, "poll_count": poll_count, "result": data}
        await asyncio.sleep(1)
    return {"status": "timeout_wait", "poll_count": poll_count, "result": last}


async def run_load_test(base: str, token: str, slug: str, skill: str, chat_path: str | None) -> dict:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    mcp_url = f"{base}/api/v1/expert/mcp/{slug}"
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()
    accept_5xx = 0
    tasks: list[dict] = []

    async with httpx.AsyncClient(timeout=60.0) as client:
        async def start_one(index: int) -> dict:
            nonlocal accept_5xx
            idem = f"loadtest-20-{uuid.uuid4()}"
            result = await _jsonrpc_call(
                client,
                mcp_url,
                {**headers, "X-Idempotency-Key": idem},
                "tools/call",
                {"name": skill, "arguments": {"prompt": f"load-test-{index}"}},
            )
            if result["http_status"] >= 500:
                accept_5xx += 1
            body = result["body"]
            structured = ((body.get("result") or {}).get("structuredContent")) or {}
            return {
                "index": index,
                "http_status": result["http_status"],
                "task_id": structured.get("task_id"),
                "error": body.get("error"),
                "idempotency_key": idem,
            }

        started_tasks = await asyncio.gather(*[start_one(i) for i in range(20)])
        for item in started_tasks:
            task_id = item.get("task_id")
            if not task_id:
                item["terminal_status"] = "not_accepted"
                tasks.append(item)
                continue
            waited = await _wait_terminal(client, base, headers, task_id, timeout_s=180)
            item["terminal_status"] = waited["status"]
            item["poll_count"] = waited["poll_count"]
            tasks.append(item)

        chat_probe = {"executed": False, "failure_rate": None, "samples": 0}
        if chat_path:
            failures = 0
            samples = 5
            for _ in range(samples):
                response = await client.post(
                    f"{base}{chat_path}",
                    headers=headers,
                    json={"prompt": "ping"},
                )
                if response.status_code >= 400:
                    failures += 1
            chat_probe = {
                "executed": True,
                "samples": samples,
                "failure_rate": failures / samples,
            }

    counts = {"accepted": 0, "running": 0, "completed": 0, "failed": 0, "cancelled": 0, "other": 0}
    for item in tasks:
        status = item.get("terminal_status")
        if item.get("task_id"):
            counts["accepted"] += 1
        if status in counts:
            counts[status] += 1
        elif status == "timeout_wait":
            counts["running"] += 1
        else:
            counts["other"] += 1

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    terminal = counts["completed"] + counts["failed"] + counts["cancelled"]
    chat_fail = chat_probe.get("failure_rate")
    passed = (
        terminal >= THRESHOLDS["min_terminal"]
        and accept_5xx <= THRESHOLDS["max_accept_http_5xx"]
        and (chat_fail is None or chat_fail <= THRESHOLDS["max_chat_failure_rate"])
    )
    return {
        "executed": True,
        "passed": passed,
        "loadGate": "met" if passed else "unmet",
        "startedAt": started,
        "elapsedMs": elapsed_ms,
        "environment": os.environ.get("WORK_EXPERT_LOADTEST_ENV", "unspecified"),
        "baseUrlHost": base.split("://", 1)[-1].split("/", 1)[0],
        "thresholds": THRESHOLDS,
        "counts": counts,
        "acceptHttp5xx": accept_5xx,
        "chatProbe": chat_probe,
        "taskIds": [item.get("task_id") for item in tasks],
        "tasks": tasks,
        "worker": {
            "batchSize": 5,
            "sequential": True,
            "replicas": os.environ.get("WORK_EXPERT_LOADTEST_WORKER_REPLICAS", "unknown"),
        },
    }


def skipped_evidence(reason: str) -> dict:
    return {
        "executed": False,
        "passed": False,
        "loadGate": "unmet",
        "reason": reason,
        "recordedAt": datetime.now(timezone.utc).isoformat(),
        "thresholds": THRESHOLDS,
        "counts": {
            "accepted": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        },
        "worker": {"batchSize": 5, "sequential": True, "replicas": "not_measured"},
        "chatProbe": {"executed": False, "failure_rate": None},
        "taskIds": [],
        "notes": [
            "Do not set capabilities.loadGate=met without executed=true and passed=true.",
            "Queue config limits are not throughput evidence.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="WORK-EXPERT-CONTRACT 20 concurrent Expert Run load test")
    parser.add_argument("--output", default=str(DEFAULT_EVIDENCE))
    args = parser.parse_args()
    base = _env("WORK_EXPERT_LOADTEST_BASE_URL")
    token = _env("WORK_EXPERT_LOADTEST_TOKEN")
    slug = _env("WORK_EXPERT_LOADTEST_SLUG")
    skill = _env("WORK_EXPERT_LOADTEST_SKILL")
    chat_path = _env("WORK_EXPERT_LOADTEST_CHAT_PATH")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    if not all([base, token, slug, skill]):
        payload = skipped_evidence(
            "Missing WORK_EXPERT_LOADTEST_BASE_URL / TOKEN / SLUG / SKILL; not executed in this environment."
        )
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise SystemExit(2)

    payload = asyncio.run(run_load_test(base, token, slug, skill, chat_path))
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(0 if payload.get("passed") else 1)


if __name__ == "__main__":
    main()

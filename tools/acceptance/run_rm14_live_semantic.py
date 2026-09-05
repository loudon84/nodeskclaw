#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_rm13_live_native as rm13

CANONICAL_PHASES = frozenset(
    {
        "PREPARING",
        "RUNTIME_STARTING",
        "RUNTIME_RUNNING",
        "WAITING_APPROVAL",
        "STOPPING",
        "RECONCILING",
    }
)

EVENTS_QUERY = r"""
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
        SELECT event_type, event_seq, payload
        FROM "{schema}".run_events
        WHERE run_id = :run_id
        ORDER BY event_seq ASC
        '''
    )
    async with engine.connect() as conn:
        rows = (await conn.execute(sql, {"run_id": run_id})).mappings().all()
    await engine.dispose()
    items = []
    for row in rows:
        payload = row["payload"]
        if hasattr(payload, "keys"):
            payload = dict(payload)
        items.append(
            {
                "event_type": row["event_type"],
                "event_seq": int(row["event_seq"] or 0),
                "payload": payload if isinstance(payload, dict) else {},
            }
        )
    print(json.dumps({"found": True, "items": items}, default=str))


asyncio.run(main())
"""


def query_sot_events(run_id: str) -> list[dict[str, Any]]:
    env = os.environ.copy()
    completed = subprocess.run(
        ["uv", "--directory", "nodeskclaw-agent", "run", "python", "-c", EVENTS_QUERY, run_id],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "")[-400:]
        raise rm13.LiveBlocked("RM14_LIVE_V13_BLOCKED", f"SoT query failed: {detail}")
    line = (completed.stdout or "").strip().splitlines()[-1] if completed.stdout.strip() else ""
    parsed = json.loads(line)
    items = parsed.get("items") if isinstance(parsed, dict) else None
    if not isinstance(items, list):
        raise rm13.LiveBlocked("RM14_LIVE_V13_BLOCKED", "SoT query returned no items")
    return items


def wait_for_progress_phase(run_id: str, timeout: int) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout
    last: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        last = query_sot_events(run_id)
        progress = [item for item in last if item.get("event_type") == "run.progress"]
        if any(
            isinstance(item.get("payload"), dict) and str(item["payload"].get("phase") or "").upper() in CANONICAL_PHASES
            for item in progress
        ):
            return last
        time.sleep(0.5)
    raise rm13.LiveBlocked(
        "RM14_LIVE_V13_BLOCKED",
        "agent SoT run.progress missing canonical phase; deploy RM-14 Adapter before V13",
    )


def evaluate_sot(items: list[dict[str, Any]]) -> dict[str, Any]:
    dumped = json.dumps(items, ensure_ascii=False)
    progress_phases = [
        str(item["payload"].get("phase") or "").upper()
        for item in items
        if item.get("event_type") == "run.progress" and isinstance(item.get("payload"), dict)
    ]
    assistant_count = sum(1 for item in items if item.get("event_type") == "assistant.message")
    return {
        "progress_has_canonical_phase": any(phase in CANONICAL_PHASES for phase in progress_phases),
        "progress_phases": sorted(set(progress_phases)),
        "assistant_message_count": assistant_count,
        "reasoning_summary_count": sum(1 for item in items if item.get("event_type") == "reasoning.summary"),
        "correlation_confidence_in_sot": "correlation_confidence" in dumped,
        "output_tail_in_sot": "output_tail" in dumped,
        "event_types": [str(item.get("event_type")) for item in items],
    }


# @lat: [[architecture/skill-agent#RM-14 Live Semantic V13]]
def run_live() -> dict[str, Any]:
    base = rm13.run_live()
    if base.get("result") != "PASS":
        raise rm13.LiveBlocked("RM14_LIVE_V13_BLOCKED", "RM-13 native live path did not PASS")
    run_id = str(base.get("run_id") or "")
    timeout = min(20, rm13.timeout_seconds())
    try:
        items = wait_for_progress_phase(run_id, timeout)
    except rm13.LiveBlocked as exc:
        observed = query_sot_events(run_id)
        progress_keys = sorted(
            {
                key
                for item in observed
                if item.get("event_type") == "run.progress" and isinstance(item.get("payload"), dict)
                for key in item["payload"].keys()
            }
        )
        raise rm13.LiveBlocked(
            exc.code,
            f"{exc}: run_id={run_id} progress_payload_keys={progress_keys}",
        ) from exc
    sot = evaluate_sot(items)
    evidence = {
        "schema": "smc.rm14.live-v13.v1",
        "policy": "REAL_PROCESS",
        "result": "FAIL",
        "timestamp": rm13.utcnow(),
        "hermes_runtime_version": base.get("hermes_runtime_version"),
        "observed_version": base.get("observed_version"),
        "version_source": base.get("version_source"),
        "run_id": run_id,
        "attempt_id": base.get("attempt_id"),
        "generation": base.get("generation"),
        "native_paths_observed": base.get("native_paths_observed"),
        "chat_completions_observed": base.get("chat_completions_observed"),
        "public_runtime_identity_leak": base.get("public_runtime_identity_leak"),
        "public_leaks": base.get("public_leaks") or [],
        "sot": sot,
    }
    all_pass = (
        str(evidence["hermes_runtime_version"] or "").startswith("v2026.8.31")
        or str(evidence["hermes_runtime_version"] or "") >= "v2026.8.31"
    ) and sot["progress_has_canonical_phase"] and not sot["correlation_confidence_in_sot"] and not sot[
        "output_tail_in_sot"
    ] and not evidence["public_runtime_identity_leak"] and not evidence["chat_completions_observed"]
    evidence["result"] = "PASS" if all_pass else "FAIL"
    if not all_pass:
        evidence["blocker"] = "RM14_LIVE_V13_BLOCKED"
    secrets = (
        rm13.env_first("RM13_USER_JWT", "RM12_USER_JWT"),
        rm13.env_first("SKILL_AGENT_INTERNAL_TOKEN"),
        rm13.env_first("RM13_HERMES_API_SERVER_KEY"),
    )
    return rm13.redact(evidence, secrets)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="docs_agent/evidence/RM-14-live-v13.json")
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--preflight-env", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        return rm13.self_check()
    if args.preflight_env:
        missing = rm13.missing_live_vars()
        if missing:
            print("REAL_HERMES_RUNTIME_UNAVAILABLE")
            for name in missing:
                print(f"missing: {name}")
            return 2
        print("RM-14 live env complete")
        return 0
    output = Path(args.output)
    try:
        evidence = run_live()
    except rm13.LiveBlocked as exc:
        payload = {
            "schema": "smc.rm14.live-v13.v1",
            "policy": "REAL_PROCESS",
            "result": "BLOCKED",
            "blocker": exc.code,
            "message": str(exc),
            "timestamp": rm13.utcnow(),
        }
        rm13.write_output(output, payload)
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 1
    rm13.write_output(output, evidence)
    if evidence.get("result") != "PASS":
        print("RM14_LIVE_V13_BLOCKED", file=sys.stderr)
        return 1
    print("RM-14 live V13 PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import atomic_write, find_repo_root, plan_id, utc_now
from plan_state import cursor_todos, smc_todo_id
from workspace import inspect as workspace_inspect


def audit_path(root: Path, pid: str) -> Path:
    return root / ".smc" / "runs" / f"{pid}-completion-audit.json"


def precheck(plan: Path, base: str | None = None) -> dict:
    """Deterministic Plan-scoped completion precheck.

    `base` remains accepted for CLI/backward compatibility but the authoritative
    baseline is the workspace snapshot captured before implementation.
    """
    root = find_repo_root(plan)
    text = plan.read_text(encoding="utf-8")
    todos = cursor_todos(text)
    states = {
        smc_todo_id(str(item["id"])): item["status"]
        for item in todos
        if smc_todo_id(str(item["id"]))
    }
    incomplete = sorted(k for k, value in states.items() if value != "completed")
    ws = workspace_inspect(plan)
    changed = list(ws["scope_changed_files"])
    result = {
        "schema": "smc.completion.precheck.v2",
        "plan_id": plan_id(plan),
        "base_commit": ws["base_commit"],
        "requested_base": base,
        "scope_fingerprint": ws["scope_fingerprint"],
        "ambient_fingerprint": ws["ambient_fingerprint"],
        "todo_states": states,
        "incomplete_todos": incomplete,
        "changed_files": changed,
        "planned_files": list(ws["planned_files"]),
        "unexpected_changed_files": list(ws["unexpected_dirty"]),
        "ambient_mutated": list(ws["ambient_mutated"]),
        "plan_semantic_changed": bool(ws["plan_semantic_changed"]),
        "head_stable": bool(ws["head_stable"]),
        "diff_empty": not bool(changed),
        "pass": (
            not incomplete
            and bool(changed)
            and ws["pass"]
        ),
    }
    return result


def record(plan: Path, result_json: Path) -> dict:
    root = find_repo_root(plan); pid = plan_id(plan)
    raw = json.loads(result_json.read_text(encoding="utf-8"))
    required = {"total_items", "done", "changed", "deferred", "unverifiable", "scope_drift", "verdict", "summary"}
    missing = required - raw.keys()
    if missing:
        raise ValueError(f"COMPLETION_AUDIT_RESULT_INVALID: missing={sorted(missing)}")
    if str(raw["verdict"]).upper() == "PASS":
        if int(raw["deferred"]) or int(raw["unverifiable"]) or int(raw["scope_drift"]) or int(raw["done"]) != int(raw["total_items"]):
            raise ValueError("COMPLETION_AUDIT_PASS_INCONSISTENT")
    ws = workspace_inspect(plan)
    if not ws["pass"]:
        raise ValueError("COMPLETION_AUDIT_WORKSPACE_UNSTABLE")
    rec = dict(raw)
    rec.update({
        "schema": "smc.completion.audit.v2",
        "plan_id": pid,
        "scope_fingerprint": ws["scope_fingerprint"],
        "ambient_fingerprint": ws["ambient_fingerprint"],
        "timestamp": utc_now(),
    })
    atomic_write(audit_path(root, pid), json.dumps(rec, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return rec


def check(plan: Path) -> tuple[str, dict | None]:
    root = find_repo_root(plan); path = audit_path(root, plan_id(plan))
    if not path.is_file():
        return "MISSING", None
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "INVALID", None
    ws = workspace_inspect(plan)
    if rec.get("scope_fingerprint") != ws["scope_fingerprint"]:
        return "STALE", rec
    if rec.get("ambient_fingerprint") != ws["ambient_fingerprint"] or not ws["ambient_stable"]:
        return "STALE", rec
    if not ws["head_stable"] or ws["unexpected_dirty"] or ws["plan_semantic_changed"]:
        return "STALE", rec
    if str(rec.get("verdict", "")).upper() != "PASS":
        return "FAILED", rec
    if any(int(rec.get(key, 0)) for key in ("deferred", "unverifiable", "scope_drift")):
        return "FAILED", rec
    return "FRESH_PASS", rec


def main() -> int:
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("precheck"); p.add_argument("--plan", required=True, type=Path); p.add_argument("--base"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("record"); p.add_argument("--plan", required=True, type=Path); p.add_argument("--result-json", required=True, type=Path)
    p = sub.add_parser("check"); p.add_argument("--plan", required=True, type=Path); p.add_argument("--json", action="store_true")
    args = ap.parse_args(); plan = args.plan.resolve()
    if not plan.is_file():
        print(f"PLAN_NOT_FOUND: {plan}", file=sys.stderr); return 2
    try:
        if args.cmd == "precheck":
            result = precheck(plan, args.base); rc = 0 if result["pass"] else 1
        elif args.cmd == "record":
            result = record(plan, args.result_json); rc = 0
        else:
            status, rec = check(plan); result = {"status": status, "record": rec}; rc = 0 if status == "FRESH_PASS" else 1
    except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr); return 1
    if getattr(args, "json", False) or args.cmd == "record":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result.get("status") or ("PASS" if result.get("pass") else "FAIL"))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

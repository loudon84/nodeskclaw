#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from common import atomic_write, find_repo_root, git, parse_first_table, plan_id, repo_relative_path, section, strip_md, utc_now
from plan_state import cursor_todos, smc_todo_id
from working_tree_fingerprint import fingerprint


def audit_path(root: Path, pid: str) -> Path:
    return root / ".smc" / "runs" / f"{pid}-completion-audit.json"


def planned_files(plan: Path) -> set[str]:
    _, rows = parse_first_table(section(plan.read_text(encoding="utf-8"), "Change Matrix"))
    out = set()
    for row in rows:
        ref = strip_md(row.get("File / Symbol", "")).replace("\\", "/")
        if ref and ref not in {"-", "None"}: out.add(ref.split("#", 1)[0])
    return out


def precheck(plan: Path, base: str) -> dict:
    root = find_repo_root(plan); text = plan.read_text(encoding="utf-8")
    todos = cursor_todos(text)
    states = {smc_todo_id(str(x["id"])): x["status"] for x in todos if smc_todo_id(str(x["id"]))}
    incomplete = sorted(k for k, v in states.items() if v != "completed")
    diff = git(root, "diff", "--name-only", base, "--").stdout.splitlines()
    untracked = git(root, "ls-files", "--others", "--exclude-standard").stdout.splitlines()
    rel_plan = repo_relative_path(plan, root)
    changed = {
        x.strip().replace("\\", "/")
        for x in [*diff, *untracked]
        if x.strip()
        and x.strip().replace("\\", "/") != rel_plan
        and not x.strip().replace("\\", "/").startswith(".smc/")
    }
    planned = planned_files(plan)
    unexpected = sorted(changed - planned)
    result = {"schema": "smc.completion.precheck.v1", "plan_id": plan_id(plan), "fingerprint": fingerprint(root), "todo_states": states, "incomplete_todos": incomplete, "changed_files": sorted(changed), "planned_files": sorted(planned), "unexpected_changed_files": unexpected, "diff_empty": not bool(changed), "pass": not incomplete and bool(changed) and not unexpected}
    return result


def record(plan: Path, result_json: Path) -> dict:
    root = find_repo_root(plan); pid = plan_id(plan)
    raw = json.loads(result_json.read_text(encoding="utf-8"))
    required = {"total_items", "done", "changed", "deferred", "unverifiable", "scope_drift", "verdict", "summary"}
    missing = required - raw.keys()
    if missing: raise ValueError(f"COMPLETION_AUDIT_RESULT_INVALID: missing={sorted(missing)}")
    if str(raw["verdict"]).upper() == "PASS":
        if int(raw["deferred"]) or int(raw["unverifiable"]) or int(raw["scope_drift"]) or int(raw["done"]) != int(raw["total_items"]):
            raise ValueError("COMPLETION_AUDIT_PASS_INCONSISTENT")
    rec = dict(raw); rec.update({"schema": "smc.completion.audit.v1", "plan_id": pid, "wtree_fingerprint": fingerprint(root), "timestamp": utc_now()})
    atomic_write(audit_path(root, pid), json.dumps(rec, ensure_ascii=False, indent=2, sort_keys=True) + "\n"); return rec


def check(plan: Path) -> tuple[str, dict | None]:
    root = find_repo_root(plan); p = audit_path(root, plan_id(plan))
    if not p.is_file(): return "MISSING", None
    rec = json.loads(p.read_text(encoding="utf-8"))
    if rec.get("wtree_fingerprint") != fingerprint(root): return "STALE", rec
    if str(rec.get("verdict", "")).upper() != "PASS": return "FAILED", rec
    if any(int(rec.get(k, 0)) for k in ("deferred", "unverifiable", "scope_drift")): return "FAILED", rec
    return "FRESH_PASS", rec


def main() -> int:
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("precheck"); p.add_argument("--plan", required=True, type=Path); p.add_argument("--base", required=True); p.add_argument("--json", action="store_true")
    p = sub.add_parser("record"); p.add_argument("--plan", required=True, type=Path); p.add_argument("--result-json", required=True, type=Path)
    p = sub.add_parser("check"); p.add_argument("--plan", required=True, type=Path); p.add_argument("--json", action="store_true")
    args = ap.parse_args(); plan = args.plan.resolve()
    if not plan.is_file(): print(f"PLAN_NOT_FOUND: {plan}", file=sys.stderr); return 2
    try:
        if args.cmd == "precheck": result = precheck(plan, args.base); rc = 0 if result["pass"] else 1
        elif args.cmd == "record": result = record(plan, args.result_json); rc = 0
        else:
            status, rec = check(plan); result = {"status": status, "record": rec}; rc = 0 if status == "FRESH_PASS" else 1
    except (ValueError, json.JSONDecodeError) as exc: print(str(exc), file=sys.stderr); return 1
    if getattr(args, "json", False) or args.cmd == "record": print(json.dumps(result, ensure_ascii=False, indent=2))
    else: print(result.get("status") or ("PASS" if result.get("pass") else "FAIL"))
    return rc


if __name__ == "__main__": raise SystemExit(main())

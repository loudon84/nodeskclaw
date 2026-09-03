#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import append_jsonl, find_repo_root, plan_id, read_jsonl, semantic_plan_sha256, utc_now
from working_tree_fingerprint import fingerprint


def path_for(root: Path, pid: str) -> Path:
    return root / ".smc" / "reviews" / f"{pid}.jsonl"


def record(kind: str, plan: Path, verdict: str, reviewer: str, note: str = "") -> dict:
    root = find_repo_root(plan)
    pid = plan_id(plan)
    rec = {
        "schema": "smc.review.v1",
        "kind": kind,
        "plan_id": pid,
        "verdict": verdict.upper(),
        "reviewer": reviewer,
        "timestamp": utc_now(),
        "note": note,
    }
    if kind == "plan": rec["plan_sha256"] = semantic_plan_sha256(plan)
    else: rec["wtree_fingerprint"] = fingerprint(root)
    append_jsonl(path_for(root, pid), rec)
    return rec


def latest_status(plan: Path, kind: str) -> tuple[str, dict | None]:
    root = find_repo_root(plan); pid = plan_id(plan)
    rows = [r for r in read_jsonl(path_for(root, pid)) if r.get("kind") == kind]
    if not rows: return "MISSING", None
    rec = rows[-1]
    if kind == "plan":
        if rec.get("plan_sha256") != semantic_plan_sha256(plan): return "STALE", rec
    else:
        if rec.get("wtree_fingerprint") != fingerprint(root): return "STALE", rec
    verdict = str(rec.get("verdict", "")).upper()
    return ("FRESH_PASS" if verdict == "PASS" else f"FRESH_{verdict or 'UNKNOWN'}"), rec


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for kind in ("plan", "implementation"):
        p = sub.add_parser(kind); p.add_argument("--plan", required=True, type=Path); p.add_argument("--verdict", required=True); p.add_argument("--reviewer", required=True); p.add_argument("--note", default="")
    p = sub.add_parser("check"); p.add_argument("--plan", required=True, type=Path); p.add_argument("--kind", choices=("plan", "implementation"), required=True); p.add_argument("--json", action="store_true")
    args = ap.parse_args(); plan = args.plan.resolve()
    if not plan.is_file(): print(f"PLAN_NOT_FOUND: {plan}", file=sys.stderr); return 2
    if args.cmd == "check":
        status, rec = latest_status(plan, args.kind)
        if args.json: print(json.dumps({"status": status, "record": rec}, ensure_ascii=False, indent=2))
        else: print(status)
        return 0 if status == "FRESH_PASS" else 1
    rec = record(args.cmd, plan, args.verdict, args.reviewer, args.note)
    print(json.dumps(rec, ensure_ascii=False, indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())

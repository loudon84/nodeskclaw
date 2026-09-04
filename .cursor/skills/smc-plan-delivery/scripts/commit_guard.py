#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from common import atomic_write, find_repo_root, git, plan_id, utc_now
from validate_delivery_completion import validate
from working_tree_fingerprint import fingerprint


def guard_path(root: Path, pid: str) -> Path:
    return root / ".smc" / "runs" / f"{pid}-commit-guard.json"


def capture(plan: Path) -> int:
    root = find_repo_root(plan); errors, details = validate(plan)
    if errors:
        print("\n".join(errors), file=sys.stderr); return 1
    rec = {"schema": "smc.commit.guard.v1", "plan_id": plan_id(plan), "ready_fingerprint": details["fingerprint"], "head_before": git(root, "rev-parse", "HEAD").stdout.strip(), "captured_at": utc_now()}
    atomic_write(guard_path(root, plan_id(plan)), json.dumps(rec, ensure_ascii=False, indent=2) + "\n")
    print(f"COMMIT_GUARD_CAPTURED fingerprint={rec['ready_fingerprint']}"); return 0


def non_smc_dirty(root: Path) -> list[str]:
    out = git(root, "status", "--porcelain=v1").stdout.splitlines()
    rows=[]
    for line in out:
        path = line[3:].strip().replace("\\", "/") if len(line) >= 4 else line
        if path.startswith(".smc/"): continue
        rows.append(line)
    return rows


def verify(plan: Path, commit: str) -> int:
    root = find_repo_root(plan); gp = guard_path(root, plan_id(plan))
    if not gp.is_file(): print("COMMIT_GUARD_MISSING", file=sys.stderr); return 1
    rec = json.loads(gp.read_text(encoding="utf-8")); current = fingerprint(root)
    if current != rec.get("ready_fingerprint"):
        print(f"COMMIT_GUARD_FINGERPRINT_MISMATCH: ready={rec.get('ready_fingerprint')} current={current}", file=sys.stderr); return 1
    exists = git(root, "cat-file", "-e", f"{commit}^{{commit}}", check=False)
    if exists.returncode: print(f"IMPLEMENTATION_COMMIT_NOT_FOUND: {commit}", file=sys.stderr); return 1
    dirty = non_smc_dirty(root)
    if dirty:
        print("POST_COMMIT_WORKTREE_DIRTY:\n" + "\n".join(dirty), file=sys.stderr); return 1
    sha = git(root, "rev-parse", commit).stdout.strip()
    rec["verified_commit"] = sha; rec["verified_at"] = utc_now(); atomic_write(gp, json.dumps(rec, ensure_ascii=False, indent=2) + "\n")
    print(f"IMPLEMENTATION_COMMIT_VERIFIED {sha} fingerprint={current}"); return 0


def main() -> int:
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd",required=True)
    p=sub.add_parser("capture");p.add_argument("plan",type=Path)
    p=sub.add_parser("verify");p.add_argument("plan",type=Path);p.add_argument("--commit",required=True)
    args=ap.parse_args();plan=args.plan.resolve()
    if not plan.is_file():print(f"PLAN_NOT_FOUND: {plan}",file=sys.stderr);return 2
    return capture(plan) if args.cmd=="capture" else verify(plan,args.commit)


if __name__=="__main__":raise SystemExit(main())

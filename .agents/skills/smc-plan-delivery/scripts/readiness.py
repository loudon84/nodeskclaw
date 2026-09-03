#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from common import find_repo_root, parse_first_table, plan_id, section, strip_md, repo_relative_path
from completion_audit import check as audit_status
from delivery_state import load as load_run
from evidence import current_status as evidence_status
from plan_state import cursor_todos, smc_todo_id, validate as todo_validate
from review_record import latest_status as review_status
from working_tree_fingerprint import fingerprint


def blocking_verifications(plan: Path) -> list[str]:
    _, rows = parse_first_table(section(plan.read_text(encoding="utf-8"), "Verification Ledger"))
    return [strip_md(r.get("Verification ID", "")).upper() for r in rows if strip_md(r.get("Blocking", "")).lower() == "yes"]


def static_status(plan: Path, root: Path) -> tuple[str, str]:
    validator = root / ".agents/skills/smc-plan-validator/scripts/validate_plan_v33.py"
    if not validator.is_file():
        return "MISSING", "validator missing"
    r = subprocess.run([sys.executable, str(validator), str(plan)], cwd=root, capture_output=True, text=True)
    detail = (r.stdout + r.stderr).strip().replace("\n", " | ")
    return ("PASS" if r.returncode == 0 else "FAIL"), detail


def collect(plan: Path) -> dict:
    root = find_repo_root(plan)
    static, static_detail = static_status(plan, root)
    plan_review, _ = review_status(plan, "plan")
    implementation_review, _ = review_status(plan, "implementation")
    completion, _ = audit_status(plan)
    todo_errors = todo_validate(plan)
    todo_rows = [
        {"todo": smc_todo_id(str(x["id"])), "cursor_id": x["id"], "status": x["status"]}
        for x in cursor_todos(plan.read_text(encoding="utf-8"))
    ]
    done = sum(1 for x in todo_rows if x["status"] == "completed")
    evid = {vid: evidence_status(plan, vid)[0] for vid in blocking_verifications(plan)}
    run = load_run(plan) or {}
    return {
        "schema": "smc.delivery.readiness.v1",
        "plan_id": plan_id(plan),
        "plan": repo_relative_path(plan, root),
        "fingerprint": fingerprint(root),
        "run_state": run.get("state", "UNINITIALIZED"),
        "last_valid_state": run.get("last_valid_state", "UNINITIALIZED"),
        "static_gate": static,
        "static_detail": static_detail,
        "semantic_gate": plan_review,
        "todos": {"completed": done, "total": len(todo_rows), "rows": todo_rows, "errors": todo_errors},
        "completion_audit": completion,
        "implementation_review": implementation_review,
        "verification": evid,
        "implementation_commit": run.get("implementation_commit"),
        "roadmap": "DONE" if run.get("state") == "ROADMAP_DONE" else "PENDING",
    }


def print_table(data: dict) -> None:
    evidence = data["verification"]
    ev = ", ".join(f"{k}={v}" for k, v in evidence.items()) or "none"
    todo = data["todos"]
    print("SMC DELIVERY READINESS")
    print(f"Plan                 : {data['plan']} ({data['plan_id']})")
    print(f"Run state            : {data['run_state']}")
    print(f"Static Gate          : {data['static_gate']}")
    print(f"Semantic Gate        : {data['semantic_gate']}")
    print(f"Todos                : {todo['completed']}/{todo['total']} completed")
    print(f"Completion Audit     : {data['completion_audit']}")
    print(f"Implementation Review: {data['implementation_review']}")
    print(f"Verification         : {ev}")
    print(f"Implementation Commit: {data['implementation_commit'] or '-'}")
    print(f"Roadmap              : {data['roadmap']}")
    print(f"Fingerprint          : {data['fingerprint']}")


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("plan", type=Path); ap.add_argument("--json", action="store_true"); args = ap.parse_args()
    plan = args.plan.resolve()
    if not plan.is_file(): print(f"PLAN_NOT_FOUND: {plan}", file=sys.stderr); return 2
    data = collect(plan)
    if args.json: print(json.dumps(data, ensure_ascii=False, indent=2))
    else: print_table(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

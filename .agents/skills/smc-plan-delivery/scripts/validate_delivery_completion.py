#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from common import find_repo_root, parse_first_table, plan_id, section, strip_md
from completion_audit import check as audit_check
from evidence import current_status as evidence_status, manifest_status
from plan_state import cursor_todos, smc_todo_id, validate as validate_todos
from review_record import latest_status as review_status
from working_tree_fingerprint import fingerprint


def blocking_verifications(plan: Path) -> list[str]:
    _, rows = parse_first_table(section(plan.read_text(encoding="utf-8"), "Verification Ledger"))
    return [strip_md(r.get("Verification ID", "")).upper() for r in rows if strip_md(r.get("Blocking", "")).lower() == "yes"]


def validate(plan: Path) -> tuple[list[str], dict]:
    root = find_repo_root(plan); errors: list[str] = []
    details: dict = {"plan_id": plan_id(plan), "fingerprint": fingerprint(root)}

    todo_errors = validate_todos(plan)
    errors.extend(todo_errors)
    todos = {smc_todo_id(str(x["id"])): x["status"] for x in cursor_todos(plan.read_text(encoding="utf-8")) if smc_todo_id(str(x["id"]))}
    details["todos"] = todos
    for tid, status in todos.items():
        if status != "completed": errors.append(f"DELIVERY_TODO_NOT_COMPLETED: {tid}={status}")

    pstatus, prec = review_status(plan, "plan"); details["plan_semantic_gate"] = pstatus
    if pstatus != "FRESH_PASS": errors.append(f"DELIVERY_PLAN_REVIEW_{pstatus}")

    astatus, arec = audit_check(plan); details["completion_audit"] = astatus
    if astatus != "FRESH_PASS": errors.append(f"DELIVERY_COMPLETION_AUDIT_{astatus}")

    rstatus, rrec = review_status(plan, "implementation"); details["implementation_review"] = rstatus
    if rstatus != "FRESH_PASS": errors.append(f"DELIVERY_IMPLEMENTATION_REVIEW_{rstatus}")

    evidence = {}
    for vid in blocking_verifications(plan):
        status, rec = evidence_status(plan, vid); evidence[vid] = status
        if status != "FRESH": errors.append(f"DELIVERY_EVIDENCE_{status}: {vid}")
    details["evidence"] = evidence
    if not evidence: errors.append("DELIVERY_BLOCKING_VERIFICATION_MISSING")

    manifest_state, manifest_record, manifest_path = manifest_status(plan)
    details["evidence_manifest"] = {"status": manifest_state, "path": str(manifest_path)}
    if manifest_state != "FRESH": errors.append(f"DELIVERY_EVIDENCE_MANIFEST_{manifest_state}")

    # Re-run v3.3 static validator when installed. This catches Plan status edits or accidental schema drift.
    validator = root / ".agents" / "skills" / "smc-plan-validator" / "scripts" / "validate_plan_v33.py"
    if validator.is_file():
        proc = subprocess.run([sys.executable, str(validator), str(plan)], cwd=root, capture_output=True, text=True)
        details["static_gate"] = "PASS" if proc.returncode == 0 else "FAIL"
        if proc.returncode:
            errors.append("DELIVERY_PLAN_STATIC_STALE: " + (proc.stdout + proc.stderr).strip().replace("\n", " | "))
    else:
        details["static_gate"] = "UNKNOWN"
        errors.append("DELIVERY_PLAN_VALIDATOR_MISSING")

    # Deduplicate, stable order.
    deduped=[]; seen=set()
    for e in errors:
        if e not in seen: seen.add(e); deduped.append(e)
    details["ready"] = not deduped
    return deduped, details


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("plan", type=Path); ap.add_argument("--json", action="store_true"); args = ap.parse_args()
    plan = args.plan.resolve()
    if not plan.is_file(): print(f"PLAN_NOT_FOUND: {plan}", file=sys.stderr); return 2
    errors, details = validate(plan)
    if args.json: print(json.dumps({"valid": not errors, "errors": errors, "details": details}, ensure_ascii=False, indent=2))
    elif errors: print("\n".join(errors), file=sys.stderr)
    else: print(f"DELIVERY_READY_TO_COMMIT fingerprint={details['fingerprint']}")
    return 1 if errors else 0


if __name__ == "__main__": raise SystemExit(main())

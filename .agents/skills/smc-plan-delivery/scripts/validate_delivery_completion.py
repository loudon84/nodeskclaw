#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from common import find_repo_root, parse_first_table, parse_top_level_frontmatter, plan_id, section, strip_md
from completion_audit import check as audit_check
from evidence import current_status as evidence_status, manifest_status
from plan_state import cursor_todos, smc_todo_id, validate as validate_todos
from review_record import latest_status as review_status
from workspace import inspect as workspace_inspect


def blocking_verifications(plan: Path) -> list[str]:
    _, rows = parse_first_table(section(plan.read_text(encoding="utf-8"), "Verification Ledger"))
    return [strip_md(r.get("Verification ID", "")).upper() for r in rows if strip_md(r.get("Blocking", "")).lower() == "yes"]


def static_validator(root: Path, plan: Path) -> Path:
    contract = parse_top_level_frontmatter(plan.read_text(encoding="utf-8")).get("plan_contract", "")
    name = "validate_plan_v34.py" if contract == "smc.plan.v3.4" else "validate_plan_v33.py"
    return root / ".agents" / "skills" / "smc-plan-validator" / "scripts" / name


def validate(plan: Path) -> tuple[list[str], dict]:
    root = find_repo_root(plan); errors: list[str] = []; ws = workspace_inspect(plan)
    details: dict = {
        "plan_id": plan_id(plan),
        "scope_fingerprint": ws["scope_fingerprint"],
        "ambient_fingerprint": ws["ambient_fingerprint"],
        "ambient_stable": ws["ambient_stable"],
    }
    if not ws["ambient_stable"]: errors.append("DELIVERY_AMBIENT_MUTATED")
    if ws["unexpected_dirty"]: errors.append("DELIVERY_SCOPE_DRIFT: " + ", ".join(ws["unexpected_dirty"]))
    if ws["plan_semantic_changed"]: errors.append("DELIVERY_PLAN_SEMANTIC_DRIFT")
    if not ws["head_stable"]: errors.append(f"DELIVERY_HEAD_DRIFT: base={ws['base_commit']} current={ws['current_head']}")

    contract = parse_top_level_frontmatter(plan.read_text(encoding="utf-8")).get("plan_contract", "")
    details["plan_contract"] = contract
    if contract != "smc.plan.v3.4": errors.append(f"DELIVERY_PLAN_CONTRACT_NOT_CURRENT: {contract or 'missing'}")

    todo_errors = validate_todos(plan); errors.extend(todo_errors)
    todos = {smc_todo_id(str(x["id"])): x["status"] for x in cursor_todos(plan.read_text(encoding="utf-8")) if smc_todo_id(str(x["id"]))}
    details["todos"] = todos
    for tid, status in todos.items():
        if status != "completed": errors.append(f"DELIVERY_TODO_NOT_COMPLETED: {tid}={status}")

    pstatus, _ = review_status(plan, "plan"); details["plan_semantic_gate"] = pstatus
    if pstatus != "FRESH_PASS": errors.append(f"DELIVERY_PLAN_REVIEW_{pstatus}")
    astatus, _ = audit_check(plan); details["completion_audit"] = astatus
    if astatus != "FRESH_PASS": errors.append(f"DELIVERY_COMPLETION_AUDIT_{astatus}")
    rstatus, _ = review_status(plan, "implementation"); details["implementation_review"] = rstatus
    if rstatus != "FRESH_PASS": errors.append(f"DELIVERY_IMPLEMENTATION_REVIEW_{rstatus}")

    evidence = {}
    for vid in blocking_verifications(plan):
        status, _ = evidence_status(plan, vid); evidence[vid] = status
        if status != "FRESH": errors.append(f"DELIVERY_EVIDENCE_{status}: {vid}")
    details["evidence"] = evidence
    if not evidence: errors.append("DELIVERY_BLOCKING_VERIFICATION_MISSING")

    manifest_state, _, manifest_path = manifest_status(plan)
    details["evidence_manifest"] = {"status": manifest_state, "path": str(manifest_path)}
    if manifest_state != "FRESH": errors.append(f"DELIVERY_EVIDENCE_MANIFEST_{manifest_state}")

    validator = static_validator(root, plan)
    if validator.is_file():
        proc = subprocess.run([sys.executable, str(validator), str(plan)], cwd=root, capture_output=True, text=True)
        details["static_gate"] = "PASS" if proc.returncode == 0 else "FAIL"
        if proc.returncode: errors.append("DELIVERY_PLAN_STATIC_STALE: " + (proc.stdout + proc.stderr).strip().replace("\n", " | "))
    else:
        details["static_gate"] = "UNKNOWN"; errors.append("DELIVERY_PLAN_VALIDATOR_MISSING")

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
    else: print(f"DELIVERY_READY_TO_COMMIT scope={details['scope_fingerprint']}")
    return 1 if errors else 0


if __name__ == "__main__": raise SystemExit(main())

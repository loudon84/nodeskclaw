#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import atomic_write, find_repo_root, git, plan_id, utc_now, repo_relative_path
from working_tree_fingerprint import fingerprint

STATES = [
    "PLAN_CREATED",
    "PLAN_STATIC_VALID",
    "PLAN_REVIEW_CLEARED",
    "IMPLEMENTING",
    "IMPLEMENTATION_COMPLETE",
    "COMPLETION_AUDIT_PASS",
    "IMPLEMENTATION_REVIEW_PASS",
    "VERIFICATION_PASS",
    "IMPLEMENTED_AND_PROVEN",
    "IMPLEMENTATION_COMMITTED",
    "ROADMAP_DONE",
]
BLOCKED = {
    "PLAN_REVISE_REQUIRED",
    "RETURN_PRD",
    "IMPLEMENTATION_BLOCKED",
    "COMPLETION_AUDIT_BLOCKED",
    "REVIEW_BLOCKED",
    "VERIFICATION_BLOCKED",
    "ROADMAP_UPDATE_BLOCKED",
}


def state_path(plan: Path) -> Path:
    root = find_repo_root(plan)
    return root / ".smc" / "runs" / f"{plan_id(plan)}.json"


def load(plan: Path) -> dict | None:
    path = state_path(plan)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save(plan: Path, data: dict) -> None:
    data["updated_at"] = utc_now()
    data["last_fingerprint"] = fingerprint(find_repo_root(plan))
    atomic_write(state_path(plan), json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def init(plan: Path) -> dict:
    existing = load(plan)
    if existing:
        return existing
    root = find_repo_root(plan)
    head = git(root, "rev-parse", "HEAD").stdout.strip()
    data = {
        "schema": "smc.delivery.run.v1",
        "plan_id": plan_id(plan),
        "plan": repo_relative_path(plan, root),
        "state": "PLAN_CREATED",
        "last_valid_state": "PLAN_CREATED",
        "base_commit": head,
        "created_at": utc_now(),
        "events": [],
    }
    save(plan, data)
    return data


def transition(plan: Path, to: str, reason: str = "") -> dict:
    data = init(plan)
    current = str(data["state"])
    if to not in STATES and to not in BLOCKED:
        raise ValueError(f"DELIVERY_STATE_INVALID: {to}")

    if to in BLOCKED:
        if current in STATES:
            data["last_valid_state"] = current
    else:
        effective = current if current in STATES else str(data.get("last_valid_state") or "PLAN_CREATED")
        if effective not in STATES:
            effective = "PLAN_CREATED"
        current_index = STATES.index(effective)
        target_index = STATES.index(to)
        if target_index < current_index:
            raise ValueError(f"DELIVERY_STATE_REGRESSION_FORBIDDEN: {effective}->{to}")
        if target_index > current_index + 1:
            raise ValueError(f"DELIVERY_STATE_SKIP_FORBIDDEN: {effective}->{to}")
        data["last_valid_state"] = to

    data["state"] = to
    data.setdefault("events", []).append({"at": utc_now(), "from": current, "to": to, "reason": reason})
    save(plan, data)
    return data


def set_commit(plan: Path, sha: str) -> dict:
    data = init(plan)
    if data.get("state") != "IMPLEMENTED_AND_PROVEN":
        raise ValueError(f"DELIVERY_COMMIT_STATE_INVALID: state={data.get('state')} expected=IMPLEMENTED_AND_PROVEN")
    root = find_repo_root(plan)
    resolved = git(root, "rev-parse", sha, check=False)
    if resolved.returncode:
        raise ValueError(f"IMPLEMENTATION_COMMIT_NOT_FOUND: {sha}")
    full_sha = resolved.stdout.strip()
    guard = root / ".smc" / "runs" / f"{plan_id(plan)}-commit-guard.json"
    if not guard.is_file():
        raise ValueError("COMMIT_GUARD_MISSING")
    try:
        guard_data = json.loads(guard.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("COMMIT_GUARD_INVALID") from exc
    if guard_data.get("verified_commit") != full_sha:
        raise ValueError(f"COMMIT_GUARD_NOT_VERIFIED_FOR_COMMIT: {full_sha}")
    data["implementation_commit"] = full_sha
    current = data["state"]
    data["state"] = "IMPLEMENTATION_COMMITTED"
    data["last_valid_state"] = "IMPLEMENTATION_COMMITTED"
    data.setdefault("events", []).append({"at": utc_now(), "from": current, "to": "IMPLEMENTATION_COMMITTED", "reason": "commit_guard verified"})
    save(plan, data)
    return data


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("init", "inspect"):
        parser = sub.add_parser(name)
        parser.add_argument("plan", type=Path)
    parser = sub.add_parser("transition")
    parser.add_argument("plan", type=Path)
    parser.add_argument("--to", required=True)
    parser.add_argument("--reason", default="")
    parser = sub.add_parser("set-commit")
    parser.add_argument("plan", type=Path)
    parser.add_argument("--sha", required=True)
    args = ap.parse_args()
    plan = args.plan.resolve()
    if not plan.is_file():
        print(f"PLAN_NOT_FOUND: {plan}", file=sys.stderr)
        return 2
    try:
        if args.cmd == "init":
            data = init(plan)
        elif args.cmd == "inspect":
            data = init(plan)
        elif args.cmd == "transition":
            data = transition(plan, args.to, args.reason)
        else:
            data = set_commit(plan, args.sha)
    except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

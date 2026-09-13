#!/usr/bin/env python3
"""Project-level Test Asset Catalog for governed Plan verification."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from common import (
    atomic_write,
    find_repo_root,
    parse_first_table,
    parse_top_level_frontmatter,
    repo_relative_path,
    section,
    split_values,
    strip_md,
    utc_now,
)
from workspace import planned_files

SCHEMA = "smc.test-asset.v1"
DEFAULT_ROOT = "docs_agent/test-assets"
ASSET_ID = re.compile(r"^TA-[A-Z0-9][A-Z0-9._-]*$")
ACTIONS = {"REUSE", "EXTEND", "NEW"}
KINDS = {"TEST", "FIXTURE", "DRIVER", "HARNESS"}
LIVE_MODES = {"LIVE", "FAULT_INJECTION", "EXTERNAL"}
REQUIRED_COLUMNS = {
    "Verification ID",
    "Asset ID",
    "Kind",
    "Path / Entrypoint",
    "Required Capabilities",
    "Action",
    "Impact",
    "Reason",
}


def _empty(value: str) -> bool:
    return strip_md(value).lower() in {"", "-", "none", "n/a", "na"}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def asset_root(root: Path) -> Path:
    profile = root / ".agents" / "ges" / "profile.json"
    rel = DEFAULT_ROOT
    if profile.is_file():
        try:
            value = json.loads(profile.read_text(encoding="utf-8"))
            configured = str(value.get("test_asset_root") or "").strip()
            if configured:
                rel = configured.replace("\\", "/")
        except json.JSONDecodeError:
            raise ValueError("TEST_ASSET_PROFILE_INVALID")
    target = (root / rel).resolve()
    try:
        repo_relative_path(target, root)
    except ValueError as exc:
        raise ValueError("TEST_ASSET_ROOT_OUTSIDE_REPO") from exc
    return target


def manifest_path(root: Path, asset_id: str) -> Path:
    return asset_root(root) / f"{asset_id}.json"


def _read_manifest(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"TEST_ASSET_MANIFEST_INVALID: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"TEST_ASSET_MANIFEST_INVALID: {path}")
    return value


def _rel_path(root: Path, value: str) -> str:
    raw = strip_md(value).replace("\\", "/")
    if _empty(raw):
        raise ValueError("TEST_ASSET_PATH_MISSING")
    target = (root / raw).resolve()
    return repo_relative_path(target, root)


def _rows(plan: Path) -> tuple[list[str], list[dict[str, str]]]:
    return parse_first_table(section(plan.read_text(encoding="utf-8"), "Test Asset Ledger"))


def _verification_rows(plan: Path) -> dict[str, dict[str, str]]:
    _, rows = parse_first_table(section(plan.read_text(encoding="utf-8"), "Verification Ledger"))
    return {strip_md(row.get("Verification ID", "")).upper(): row for row in rows if not _empty(row.get("Verification ID", ""))}


def _scenario_subjects(plan: Path) -> dict[str, str]:
    _, rows = parse_first_table(section(plan.read_text(encoding="utf-8"), "Live Scenario Matrix"))
    out: dict[str, str] = {}
    for row in rows:
        subject = strip_md(row.get("Subject / Fixture", ""))
        for verification_id in split_values(row.get("Verification IDs", "")):
            out[verification_id.upper()] = subject
    return out


def _manifest_errors(root: Path, row: dict[str, str], require_current_digest: bool) -> list[str]:
    asset_id = strip_md(row.get("Asset ID", "")).upper()
    errors: list[str] = []
    path = manifest_path(root, asset_id)
    if not path.is_file():
        return [f"TEST_ASSET_MANIFEST_MISSING: {asset_id}"]
    try:
        data = _read_manifest(path)
    except ValueError as exc:
        return [str(exc)]
    if data.get("schema") != SCHEMA:
        errors.append(f"TEST_ASSET_MANIFEST_SCHEMA_INVALID: {asset_id}")
    if str(data.get("asset_id") or "").upper() != asset_id:
        errors.append(f"TEST_ASSET_MANIFEST_ID_MISMATCH: {asset_id}")
    if str(data.get("status") or "").upper() != "ACTIVE":
        errors.append(f"TEST_ASSET_MANIFEST_NOT_ACTIVE: {asset_id}")
    expected_kind = strip_md(row.get("Kind", "")).upper()
    if str(data.get("kind") or "").upper() != expected_kind:
        errors.append(f"TEST_ASSET_KIND_MISMATCH: {asset_id}")
    try:
        expected_path = _rel_path(root, row.get("Path / Entrypoint", ""))
    except ValueError as exc:
        return errors + [str(exc)]
    if str(data.get("path") or "").replace("\\", "/") != expected_path:
        errors.append(f"TEST_ASSET_PATH_MISMATCH: {asset_id}")
    actual_path = root / expected_path
    if require_current_digest:
        if not actual_path.is_file():
            errors.append(f"TEST_ASSET_PATH_MISSING: {asset_id}")
        elif data.get("content_sha256") != file_sha256(actual_path):
            errors.append(f"TEST_ASSET_DIGEST_STALE: {asset_id}")
    return errors


# @lat: [[test-assets#GES Test Assets#Project Catalog]]
def validate_plan(plan: Path, require_synced: bool = False) -> list[dict[str, str]]:
    """Validate v3.6 Test Asset Ledger entries without changing project state."""
    root = find_repo_root(plan)
    contract = parse_top_level_frontmatter(plan.read_text(encoding="utf-8")).get("plan_contract", "")
    if contract != "smc.plan.v3.6":
        return []
    header, rows = _rows(plan)
    errors: list[dict[str, str]] = []

    def add(code: str, detail: str) -> None:
        errors.append({"code": code, "detail": detail})

    if not REQUIRED_COLUMNS.issubset(set(header)):
        missing = ", ".join(sorted(REQUIRED_COLUMNS - set(header)))
        add("PLAN_TEST_ASSET_LEDGER_INVALID", f"missing columns: {missing}")
        return errors

    verification = _verification_rows(plan)
    subjects = _scenario_subjects(plan)
    planned = planned_files(plan)
    by_verification: dict[str, list[dict[str, str]]] = {}
    seen_assets: set[str] = set()
    for index, row in enumerate(rows, 1):
        vid = strip_md(row.get("Verification ID", "")).upper()
        asset_id = strip_md(row.get("Asset ID", "")).upper()
        kind = strip_md(row.get("Kind", "")).upper()
        action = strip_md(row.get("Action", "")).upper()
        if not vid or vid not in verification:
            add("PLAN_TEST_ASSET_VERIFICATION_UNKNOWN", f"row {index}: {vid or '<empty>'}")
            continue
        if not ASSET_ID.fullmatch(asset_id):
            add("PLAN_TEST_ASSET_ID_INVALID", f"{vid}: {asset_id or '<empty>'}")
            continue
        if kind not in KINDS:
            add("PLAN_TEST_ASSET_KIND_INVALID", f"{asset_id}: {kind or '<empty>'}")
        if action not in ACTIONS:
            add("PLAN_TEST_ASSET_ACTION_INVALID", f"{asset_id}: {action or '<empty>'}")
        if _empty(row.get("Required Capabilities", "")):
            add("PLAN_TEST_ASSET_CAPABILITIES_MISSING", asset_id)
        if _empty(row.get("Impact", "")) or _empty(row.get("Reason", "")):
            add("PLAN_TEST_ASSET_DECISION_INCOMPLETE", asset_id)
        if asset_id in seen_assets and action == "NEW":
            add("PLAN_TEST_ASSET_DUPLICATE_NEW", asset_id)
        seen_assets.add(asset_id)
        by_verification.setdefault(vid, []).append(row)

        try:
            asset_path = _rel_path(root, row.get("Path / Entrypoint", ""))
        except ValueError as exc:
            add("PLAN_TEST_ASSET_PATH_INVALID", f"{asset_id}: {exc}")
            continue
        asset_manifest = repo_relative_path(manifest_path(root, asset_id), root)
        if action == "REUSE":
            for issue in _manifest_errors(root, row, require_current_digest=True):
                add(issue.split(":", 1)[0], issue)
            if asset_path in planned or asset_manifest in planned:
                add("PLAN_TEST_ASSET_REUSE_MUTATED", asset_id)
        elif action == "EXTEND":
            for issue in _manifest_errors(root, row, require_current_digest=False):
                add(issue.split(":", 1)[0], issue)
            if asset_path not in planned or asset_manifest not in planned:
                add("PLAN_TEST_ASSET_EXTEND_NOT_OWNED", asset_id)
            if strip_md(verification[vid].get("Evidence Action", "")).upper() == "REUSE_EVIDENCE":
                add("PLAN_TEST_ASSET_EXTEND_REQUIRES_RERUN", asset_id)
        elif action == "NEW":
            if manifest_path(root, asset_id).exists():
                add("PLAN_TEST_ASSET_NEW_ALREADY_EXISTS", asset_id)
            if asset_path not in planned or asset_manifest not in planned:
                add("PLAN_TEST_ASSET_NEW_NOT_OWNED", asset_id)
            if strip_md(verification[vid].get("Evidence Action", "")).upper() == "REUSE_EVIDENCE":
                add("PLAN_TEST_ASSET_NEW_REQUIRES_EVIDENCE", asset_id)

    for vid, row in verification.items():
        mode = strip_md(row.get("Acceptance Mode", "")).upper()
        evidence_action = strip_md(row.get("Evidence Action", "")).upper()
        subject = subjects.get(vid, "")
        if mode in LIVE_MODES and evidence_action != "REUSE_EVIDENCE" and not _empty(subject):
            linked = by_verification.get(vid, [])
            if len(linked) != 1:
                add("PLAN_TEST_ASSET_BINDING_REQUIRED", vid)
            elif strip_md(linked[0].get("Asset ID", "")).upper() != subject.upper():
                add("PLAN_TEST_ASSET_SUBJECT_MISMATCH", f"{vid}: {subject}")
    return errors


# @lat: [[test-assets#GES Test Assets#Delivery Synchronization]]
def sync(plan: Path) -> list[dict[str, str]]:
    """Materialize NEW/EXTEND manifests after their Plan-owned test files exist."""
    root = find_repo_root(plan)
    errors = validate_plan(plan, require_synced=False)
    if errors:
        return errors
    _, rows = _rows(plan)
    for row in rows:
        action = strip_md(row.get("Action", "")).upper()
        if action not in {"NEW", "EXTEND"}:
            continue
        asset_id = strip_md(row.get("Asset ID", "")).upper()
        rel = _rel_path(root, row.get("Path / Entrypoint", ""))
        target = root / rel
        if not target.is_file():
            return [{"code": "TEST_ASSET_PATH_MISSING", "detail": asset_id}]
        payload = {
            "schema": SCHEMA,
            "asset_id": asset_id,
            "status": "ACTIVE",
            "kind": strip_md(row.get("Kind", "")).upper(),
            "path": rel,
            "capabilities": split_values(row.get("Required Capabilities", "")),
            "content_sha256": file_sha256(target),
            "updated_at": utc_now(),
        }
        atomic_write(manifest_path(root, asset_id), json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return validate_plan(plan, require_synced=True)


def resolved_assets(plan: Path) -> list[dict]:
    root = find_repo_root(plan)
    _, rows = _rows(plan)
    resolved: list[dict] = []
    for row in rows:
        asset_id = strip_md(row.get("Asset ID", "")).upper()
        path = manifest_path(root, asset_id)
        if path.is_file():
            data = _read_manifest(path)
            resolved.append({
                "asset_id": asset_id,
                "action": strip_md(row.get("Action", "")).upper(),
                "manifest": repo_relative_path(path, root),
                "content_sha256": data.get("content_sha256"),
            })
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "sync", "status"):
        command = sub.add_parser(name)
        command.add_argument("--plan", required=True, type=Path)
        command.add_argument("--json", action="store_true")
    args = parser.parse_args()
    plan = args.plan.resolve()
    if not plan.is_file():
        print("PLAN_NOT_FOUND: " + str(plan), file=sys.stderr)
        return 2
    if args.command == "sync":
        errors = sync(plan)
        payload = {"valid": not errors, "errors": errors, "assets": resolved_assets(plan)}
    elif args.command == "status":
        errors = validate_plan(plan, require_synced=True)
        payload = {"valid": not errors, "errors": errors, "assets": resolved_assets(plan)}
    else:
        errors = validate_plan(plan, require_synced=False)
        payload = {"valid": not errors, "errors": errors}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif errors:
        print("\n".join(f"{error['code']}: {error['detail']}" for error in errors), file=sys.stderr)
    else:
        print("TEST ASSET " + args.command.upper() + " PASS")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

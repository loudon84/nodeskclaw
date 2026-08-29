#!/usr/bin/env python3
"""Skill Run Contract Generator & Release Helper.
Validates artifacts, updates SHA256 in manifest.json, and supports release checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIR = ROOT / "nodeskclaw-backend" / "contracts" / "skill-run" / "v1.0.0"
MANIFEST_PATH = CONTRACT_DIR / "manifest.json"


def get_git_head() -> str:
    try:
        res = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        return res
    except Exception:
        return "0000000000000000000000000000000000000000"


def calculate_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def update_manifest(commit_hash: str | None = None) -> dict:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_PATH}")

    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    artifacts = data.get("artifacts") or {}

    new_artifacts = {}
    for rel_path in sorted(artifacts.keys()):
        file_path = CONTRACT_DIR / rel_path
        if not file_path.exists():
            raise FileNotFoundError(f"Contract artifact missing: {file_path}")
        new_artifacts[rel_path] = calculate_sha256(file_path)

    data["artifacts"] = new_artifacts
    if commit_hash:
        data["backendCommit"] = commit_hash
    data["generatedAt"] = datetime.now(timezone.utc).isoformat()

    MANIFEST_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Updated contract manifest at {MANIFEST_PATH}")
    return data


def check_contracts() -> bool:
    if not MANIFEST_PATH.exists():
        print("Manifest missing!", file=sys.stderr)
        return False
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    artifacts = data.get("artifacts") or {}
    all_ok = True
    for rel_path, expected_sha in artifacts.items():
        file_path = CONTRACT_DIR / rel_path
        if not file_path.exists():
            print(f"MISSING: {rel_path}", file=sys.stderr)
            all_ok = False
            continue
        actual_sha = calculate_sha256(file_path)
        if actual_sha != expected_sha:
            print(f"DRIFT: {rel_path} expected={expected_sha} actual={actual_sha}", file=sys.stderr)
            all_ok = False
    if all_ok:
        print("All contract artifacts match manifest checksums.")
    return all_ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Skill Run Contract Helper")
    parser.add_argument("--check", action="store_true", help="Check for contract drift")
    parser.add_argument("--update", action="store_true", help="Update checksums in manifest")
    parser.add_argument("--commit", help="Bind specific commit hash")
    args = parser.parse_args()

    if args.check:
        if not check_contracts():
            sys.exit(1)
        return

    commit = args.commit or get_git_head()
    update_manifest(commit)


if __name__ == "__main__":
    main()

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVIDENCE_DIR = Path("docs_agent/evidence/remote-acp-v2")


def write_evidence(
    *,
    acceptance_id: str,
    status: str,
    requirement_ids: list[str],
    test_ids: list[str],
    repository: str,
    commit_sha: str,
    command: str,
    exit_code: int,
    oracle: dict[str, Any],
    contract_versions: dict[str, str],
    evidence_files: list[str] | None = None,
    dest_dir: Path | None = None,
) -> Path:
    if status == "PASS" and (not commit_sha or len(commit_sha) != 40):
        raise ValueError("commit_sha required for PASS")
    if status in {"BLOCKED", "SKIPPED"}:
        raise ValueError("BLOCKED/SKIPPED cannot be written as PASS")
    payload = {
        "acceptance_id": acceptance_id,
        "status": status,
        "requirement_ids": requirement_ids,
        "test_ids": test_ids,
        "repository": repository,
        "commit_sha": commit_sha,
        "consumer_repository": "loudon84/smc-copilot",
        "consumer_commit_sha": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "exit_code": exit_code,
        "oracle": oracle,
        "contract_versions": contract_versions,
        "evidence_files": evidence_files or [],
    }
    target_dir = dest_dir or EVIDENCE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{acceptance_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

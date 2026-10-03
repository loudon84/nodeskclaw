from __future__ import annotations

import hashlib
import json
from pathlib import Path


TASK_ROOT = Path(__file__).resolve().parents[2]
AUTO_ROOT = TASK_ROOT / "contracts/agent-automation/v1.0.0"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_agent_automation_bundle_checksums_closed():
    sums = (AUTO_ROOT / "SHA256SUMS").read_bytes()
    assert b"\r" not in sums
    listed: dict[str, str] = {}
    for line in sums.decode("utf-8").splitlines():
        if not line.strip():
            continue
        digest, _, relative = line.partition("  ")
        listed[relative] = digest
    assert "manifest.json" in listed
    actual = {
        path.relative_to(AUTO_ROOT).as_posix()
        for path in AUTO_ROOT.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    assert set(listed) == actual
    for relative, digest in listed.items():
        assert _sha256_file(AUTO_ROOT / relative) == digest


def test_agent_automation_release_documents_consumer_order():
    text = (AUTO_ROOT / "RELEASE.md").read_text(encoding="utf-8")
    assert "configure" in text.lower() or "create and enable" in text.lower()
    assert "Work UI is not implemented" in text
    assert "production_gate: unpassed" in text
    manifest = json.loads((AUTO_ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["production_gate"] == "unpassed"
    assert "agent-automation.create.v1" in manifest["schemaIds"]

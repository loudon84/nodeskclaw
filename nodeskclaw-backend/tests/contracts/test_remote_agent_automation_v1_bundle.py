from __future__ import annotations

import json
from pathlib import Path

from scripts import contracts as contracts_module


BACKEND_ROOT = Path(__file__).resolve().parents[2]
AUTO_ROOT = BACKEND_ROOT / "contracts/remote-agent-automation/v1.0.0"
REMOTE_V13_ROOT = BACKEND_ROOT / "contracts/remote-agent/v1.3.0"


def test_remote_agent_automation_bundle_checksums():
    contracts_module._validate_skill_run_checksums_exact(AUTO_ROOT)


def test_remote_agent_v13_unchanged_by_automation_bundle():
    contracts_module._validate_skill_run_checksums_exact(REMOTE_V13_ROOT)


def test_remote_agent_automation_release_consumer_and_gate():
    text = (AUTO_ROOT / "RELEASE.md").read_text(encoding="utf-8")
    assert "Work UI is not implemented" in text
    assert "production_gate: unpassed" in text
    assert "X-Autotask-Internal-Token" in text
    manifest = json.loads((AUTO_ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["contractVersion"] == "1.0.0"
    assert manifest["production_gate"] == "unpassed"
    assert manifest["acp"] == "unsupported"

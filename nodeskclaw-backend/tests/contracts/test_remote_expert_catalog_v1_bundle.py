from pathlib import Path
import hashlib

from scripts import contracts as contracts_module


BACKEND_ROOT = Path(__file__).resolve().parents[2]
CATALOG_ROOT = BACKEND_ROOT / "contracts/remote-expert-catalog/v1.0.0"
REMOTE_V15 = BACKEND_ROOT / "contracts/remote-agent/v1.5.0"


def test_remote_expert_catalog_bundle_checksums():
    contracts_module._validate_skill_run_checksums_exact(CATALOG_ROOT)


def test_remote_agent_v15_pin_unchanged():
    digest = hashlib.sha256((REMOTE_V15 / "SHA256SUMS").read_bytes()).hexdigest()
    assert digest == "c8bc0ed8a1cf5b21fcbfb743a59a2d24480ff4dc90a651e8a0b5c057ca27b18c"


def test_catalog_release_has_no_skill_name():
    text = (CATALOG_ROOT / "RELEASE.md").read_text(encoding="utf-8")
    assert "expert:invoke" in text
    assert "skillName" not in text

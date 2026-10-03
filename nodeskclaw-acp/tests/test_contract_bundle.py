from pathlib import Path

from app.constants import REMOTE_AGENT_CONTRACT_DIGEST, REMOTE_AGENT_CONTRACT_VERSION


def test_contract_bundle_pins_remote_agent_v15():
    root = Path(__file__).resolve().parents[1] / "contracts" / "acp-v1-adapter" / "v1.0.0"
    release = (root / "RELEASE.md").read_text(encoding="utf-8")
    assert "ACP_V1_ADAPTER_PROFILE_CONFORMANT" in release
    assert "FULL_ACP_V1_CONFORMANT" in release
    assert REMOTE_AGENT_CONTRACT_DIGEST in release
    manifest = (root / "manifest.json").read_text(encoding="utf-8")
    assert REMOTE_AGENT_CONTRACT_VERSION in manifest
    assert REMOTE_AGENT_CONTRACT_DIGEST in manifest
    assert (root / "SHA256SUMS").exists()

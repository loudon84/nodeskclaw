import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CATALOG = REPO / "nodeskclaw-backend/contracts/remote-expert-catalog/v1.1.0"
GATEWAY = REPO / "nodeskclaw-backend/contracts/remote-acp-gateway/v1.0.0"
RUNTIME = REPO / "nodeskclaw-agent/contracts/acp-runtime-gateway/v1.0.0"
AGGREGATE = REPO / "contracts/remote-expert-frontend/v2.0.0"
V1_AGGREGATE = REPO / "contracts/remote-expert-frontend/v1.0.0"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v2_bundles_have_sha256sums():
    for root in (CATALOG, GATEWAY, RUNTIME, AGGREGATE):
        assert (root / "SHA256SUMS").is_file()
        assert b"\r" not in (root / "SHA256SUMS").read_bytes()


def test_frontend_v2_pins_public_only():
    pins = json.loads((AGGREGATE / "component-pins.json").read_text(encoding="utf-8"))
    assert set(pins) == {"remoteExpertCatalog", "remoteAcpGateway"}
    assert "acpAdapter" not in pins
    assert "remoteAgent" not in pins


def test_v1_frontend_digest_unchanged():
    manifest = json.loads((V1_AGGREGATE / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundleDigest"] == "598ae09bb681049b42dbca509ff32394aaed81b1b826fab243de78cd3ff090cd"


def test_consumer_forbids_legacy_adapter():
    consumer = json.loads((AGGREGATE / "consumer/smc-copilot-v6.3.json").read_text(encoding="utf-8"))
    assert "nodeskclaw-acp.exe" in consumer["forbiddenDependencies"]

import hashlib
import json
import re
from pathlib import Path

from app.constants import (
    ADAPTER_CONTRACT_DIGEST,
    CATALOG_CONTRACT_DIGEST,
    REMOTE_AGENT_CONTRACT_DIGEST,
)

IMPLEMENTATION_COMMIT = "896450ad479033afc2428852a2d02f70f77ab19e"
ACP_V11 = Path(__file__).resolve().parents[1] / "contracts/acp-v1-adapter/v1.1.0"
CATALOG_ROOT = (
    Path(__file__).resolve().parents[2]
    / "nodeskclaw-backend/contracts/remote-expert-catalog/v1.0.0"
)
REMOTE_V15 = (
    Path(__file__).resolve().parents[2]
    / "nodeskclaw-backend/contracts/remote-agent/v1.5.0"
)
REMOTE_AGENT_DIGEST_LF = "9bb6b0cd316a8ceab2824a259edfa90d033f5dcb7e56785aa0ab2698990403e3"


def _digest_materializations(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    lf = raw.replace(b"\r\n", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    return hashlib.sha256(lf).hexdigest(), hashlib.sha256(crlf).hexdigest()


def test_v11_has_resume_and_resource_link():
    release = (ACP_V11 / "RELEASE.md").read_text(encoding="utf-8")
    assert "resume" in release.lower()
    mapping = (ACP_V11 / "mapping/resource-link-mapping.json").read_text(encoding="utf-8")
    assert "nodeskclaw://attachment" in mapping
    sums = (ACP_V11 / "SHA256SUMS").read_text(encoding="utf-8")
    assert "golden/session-resume.json" in sums


def test_v11_implementation_identity():
    manifest = json.loads((ACP_V11 / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["implementationHeadSha"] == IMPLEMENTATION_COMMIT
    assert manifest["releaseCommitSha"] == IMPLEMENTATION_COMMIT
    assert manifest["production_gate"] == "unpassed"
    assert manifest["contractVersion"] == "1.1.0"


def test_v11_consumer_digest_matches_runtime_constant():
    digest = hashlib.sha256((ACP_V11 / "SHA256SUMS").read_bytes()).hexdigest()
    assert digest == ADAPTER_CONTRACT_DIGEST
    assert digest != "b4de0c63a370810403e18438618430ba8cac9bd790747d567937585812f13f8a"


def test_v11_pins_final_catalog_digest():
    manifest = json.loads((ACP_V11 / "manifest.json").read_text(encoding="utf-8"))
    catalog_digest = hashlib.sha256((CATALOG_ROOT / "SHA256SUMS").read_bytes()).hexdigest()
    assert catalog_digest == CATALOG_CONTRACT_DIGEST
    assert manifest["catalogContractDigest"] == catalog_digest
    assert manifest["catalogContractDigest"] == CATALOG_CONTRACT_DIGEST


def test_v11_remote_agent_pin_dual_materialization():
    manifest = json.loads((ACP_V11 / "manifest.json").read_text(encoding="utf-8"))
    lf_digest, crlf_digest = _digest_materializations(REMOTE_V15 / "SHA256SUMS")
    assert REMOTE_AGENT_CONTRACT_DIGEST in {lf_digest, crlf_digest}
    assert REMOTE_AGENT_DIGEST_LF in {lf_digest, crlf_digest}
    assert manifest["remoteAgentContractDigest"] == REMOTE_AGENT_CONTRACT_DIGEST


def test_version_json_exposes_final_adapter_digest():
    text = Path(__file__).resolve().parents[1].joinpath("app/constants.py").read_text(encoding="utf-8")
    match = re.search(r'ADAPTER_CONTRACT_DIGEST = "([0-9a-f]{64})"', text)
    assert match is not None
    assert match.group(1) == ADAPTER_CONTRACT_DIGEST

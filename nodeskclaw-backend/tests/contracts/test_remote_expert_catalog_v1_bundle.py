from pathlib import Path
import hashlib
import json

from scripts import contracts as contracts_module


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
CATALOG_ROOT = BACKEND_ROOT / "contracts/remote-expert-catalog/v1.0.0"
REMOTE_V15 = BACKEND_ROOT / "contracts/remote-agent/v1.5.0"
ACP_CONSTANTS = REPO_ROOT / "nodeskclaw-acp/app/constants.py"
IMPLEMENTATION_COMMIT = "896450ad479033afc2428852a2d02f70f77ab19e"
REMOTE_AGENT_DIGEST_CRLF = "c8bc0ed8a1cf5b21fcbfb743a59a2d24480ff4dc90a651e8a0b5c057ca27b18c"
REMOTE_AGENT_DIGEST_LF = "9bb6b0cd316a8ceab2824a259edfa90d033f5dcb7e56785aa0ab2698990403e3"


def _parse_constant(name: str) -> str:
    text = ACP_CONSTANTS.read_text(encoding="utf-8")
    marker = f'{name} = "'
    start = text.index(marker) + len(marker)
    end = text.index('"', start)
    return text[start:end]


def _digest_materializations(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    lf = raw.replace(b"\r\n", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    return hashlib.sha256(lf).hexdigest(), hashlib.sha256(crlf).hexdigest()


def _digest_ok(path: Path, expected: str) -> bool:
    raw = path.read_bytes()
    lf = raw.replace(b"\r\n", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    return expected in {
        hashlib.sha256(raw).hexdigest(),
        hashlib.sha256(lf).hexdigest(),
        hashlib.sha256(crlf).hexdigest(),
    }


def test_remote_expert_catalog_bundle_checksums():
    sums_path = CATALOG_ROOT / "SHA256SUMS"
    raw = sums_path.read_bytes()
    assert b"\r" not in raw
    listed = contracts_module._parse_sha256sums_from_text(raw.decode("utf-8"))
    actual = contracts_module._bundle_files_excluding_checksum(CATALOG_ROOT)
    assert set(listed) == actual
    for relative, digest in listed.items():
        assert _digest_ok(CATALOG_ROOT / relative, digest)


def test_catalog_implementation_identity():
    manifest = json.loads((CATALOG_ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["implementationHeadSha"] == IMPLEMENTATION_COMMIT
    assert manifest["releaseCommitSha"] == IMPLEMENTATION_COMMIT
    assert manifest["production_gate"] == "unpassed"
    assert manifest["contractName"] == "REMOTE-EXPERT-CATALOG-CONTRACT"
    assert manifest["contractVersion"] == "1.0.0"


def test_catalog_consumer_digest_matches_runtime_constant():
    digest = hashlib.sha256((CATALOG_ROOT / "SHA256SUMS").read_bytes()).hexdigest()
    assert digest == _parse_constant("CATALOG_CONTRACT_DIGEST")
    assert digest != "cd38f8fbed0b41632fb0e7bbb7d6218ce6330d2cb2797555e9e6e62e14c38dba"


def test_remote_agent_v15_pin_dual_materialization():
    lf_digest, crlf_digest = _digest_materializations(REMOTE_V15 / "SHA256SUMS")
    assert REMOTE_AGENT_DIGEST_CRLF in {lf_digest, crlf_digest}
    assert REMOTE_AGENT_DIGEST_LF in {lf_digest, crlf_digest}
    assert _parse_constant("REMOTE_AGENT_CONTRACT_DIGEST") == REMOTE_AGENT_DIGEST_CRLF


def test_catalog_release_has_no_skill_name():
    text = (CATALOG_ROOT / "RELEASE.md").read_text(encoding="utf-8")
    assert "expert:invoke" in text
    assert "skillName" not in text

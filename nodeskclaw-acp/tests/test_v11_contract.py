from pathlib import Path

ACP_V11 = Path(__file__).resolve().parents[1] / "contracts/acp-v1-adapter/v1.1.0"


def test_v11_has_resume_and_resource_link():
    release = (ACP_V11 / "RELEASE.md").read_text(encoding="utf-8")
    assert "resume" in release.lower()
    mapping = (ACP_V11 / "mapping/resource-link-mapping.json").read_text(encoding="utf-8")
    assert "nodeskclaw://attachment" in mapping
    sums = (ACP_V11 / "SHA256SUMS").read_text(encoding="utf-8")
    assert "golden/session-resume.json" in sums

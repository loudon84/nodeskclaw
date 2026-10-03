import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY = REPO_ROOT / "tools/contracts/verify_remote_expert_frontend_contract.py"
AGGREGATE = REPO_ROOT / "contracts/remote-expert-frontend/v1.0.0"
FIXTURES = REPO_ROOT / "nodeskclaw-acp/contracts/consumer-fixtures/smc-copilot-v6.3"
REQUIRED_FIXTURES = (
    "catalog.json",
    "initialize.json",
    "session-new.json",
    "session-resume.json",
    "session-close.json",
    "text-turn.json",
    "attachment-turn.json",
    "tool-call.json",
    "permission-request.json",
    "artifact-resource-link.json",
    "cancel.json",
    "remote-error.json",
)


def _run_verify(repo_root: Path, extra: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(VERIFY), "--repo-root", str(repo_root)]
    if extra:
        cmd.extend(extra)
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")


def test_validator_pass_on_repo():
    completed = _run_verify(REPO_ROOT)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["implementationCommit"] == "896450ad479033afc2428852a2d02f70f77ab19e"
    assert payload["productionGate"] == "unpassed"
    assert payload["acpConsumerDigest"] != "b4de0c63a370810403e18438618430ba8cac9bd790747d567937585812f13f8a"
    assert payload["catalogConsumerDigest"] != "cd38f8fbed0b41632fb0e7bbb7d6218ce6330d2cb2797555e9e6e62e14c38dba"


def test_golden_consumer_fixtures_present():
    missing = [name for name in REQUIRED_FIXTURES if not (FIXTURES / name).is_file()]
    assert missing == []
    catalog = json.loads((FIXTURES / "catalog.json").read_text(encoding="utf-8"))
    assert "skillName" not in json.dumps(catalog)


def test_consumer_descriptor_forbids_work_expert_and_skill_run():
    consumer = json.loads((AGGREGATE / "consumer/smc-copilot-v6.3.json").read_text(encoding="utf-8"))
    forbidden = set(consumer["forbiddenDependencies"])
    required = set(consumer["requiredCapabilities"])
    for item in (
        "WORK-EXPERT-CONTRACT",
        "ExpertProjectionStore",
        "expert.start",
        "skillName",
        "SkillRunStore",
    ):
        assert item in forbidden
        assert item not in required
    assert consumer["integrationMode"] == "original-chat-compose-acp"


def test_tamper_manifest_byte_fails(tmp_path: Path):
    copy = tmp_path / "repo"
    copy.mkdir()
    for rel in (
        "nodeskclaw-acp/contracts/acp-v1-adapter/v1.1.0",
        "nodeskclaw-backend/contracts/remote-expert-catalog/v1.0.0",
        "nodeskclaw-backend/contracts/remote-agent/v1.5.0",
        "contracts/remote-expert-frontend/v1.0.0",
        "nodeskclaw-acp/contracts/consumer-fixtures/smc-copilot-v6.3",
        "nodeskclaw-acp/app/constants.py",
        "tools/contracts/verify_remote_expert_frontend_contract.py",
    ):
        src = REPO_ROOT / rel
        dest = copy / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)
    target = copy / "nodeskclaw-acp/contracts/acp-v1-adapter/v1.1.0/manifest.json"
    text = target.read_text(encoding="utf-8")
    target.write_text(text.replace("ACP-V1-ADAPTER-CONTRACT", "ACP-V1-ADAPTER-TAMPERED", 1), encoding="utf-8")
    completed = _run_verify(copy)
    assert completed.returncode != 0
    payload = json.loads(completed.stdout)
    assert payload["ok"] is False

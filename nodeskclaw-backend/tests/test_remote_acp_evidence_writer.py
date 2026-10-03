import importlib.util
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[2] / "tools/acceptance/write_remote_acp_v2_evidence.py"


def test_evidence_writer_requires_commit(tmp_path: Path):
    spec = importlib.util.spec_from_file_location("write_remote_acp_v2_evidence", MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    path = module.write_evidence(
        acceptance_id="A-CON-001",
        status="PASS",
        requirement_ids=["REQ-CON-001"],
        test_ids=["TEST-A-CON-001"],
        repository="loudon84/nodeskclaw",
        commit_sha="a" * 40,
        command="python tools/contracts/verify_remote_expert_frontend_contract_v2.py",
        exit_code=0,
        oracle={"type": "digest", "expected": "sealed", "actual": "sealed"},
        contract_versions={"frontend": "2.0.0", "catalog": "1.1.0", "remote_acp": "1.0.0"},
        dest_dir=tmp_path,
    )
    assert path.is_file()

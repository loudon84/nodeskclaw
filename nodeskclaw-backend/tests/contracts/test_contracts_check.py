from pathlib import Path

from scripts import contracts as contracts_module
from scripts.contracts import is_empty_json_schema


def test_contract_root_and_p0_tests_exist():
    backend_root = Path(__file__).resolve().parents[2]
    for rel_path in contracts_module.P0_TEST_FILES:
        assert (backend_root / rel_path).exists(), rel_path
    assert (backend_root / "contracts/work-expert/v1.0.0/SHA256SUMS").exists()


def test_is_empty_json_schema():
    assert is_empty_json_schema({}) is True
    assert is_empty_json_schema(None) is True
    assert is_empty_json_schema({"$ref": "#/components/schemas/TaskRead"}) is False
    assert is_empty_json_schema({"type": "string", "format": "binary"}) is False


def test_skill_run_contracts_v10_and_v11_exist():
    backend_root = Path(__file__).resolve().parents[2]
    assert (backend_root / "contracts/skill-run/v1.0.0/SHA256SUMS").exists()
    assert (backend_root / "contracts/skill-run/v1.1.0/SHA256SUMS").exists()


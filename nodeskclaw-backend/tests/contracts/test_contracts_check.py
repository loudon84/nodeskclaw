from pathlib import Path

from scripts import contracts as contracts_module


def test_contract_root_and_p0_tests_exist():
    backend_root = Path(__file__).resolve().parents[2]
    for rel_path in contracts_module.P0_TEST_FILES:
        assert (backend_root / rel_path).exists(), rel_path

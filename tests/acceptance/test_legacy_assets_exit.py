from __future__ import annotations

from pathlib import Path


def test_legacy_postman_assets_not_in_default_paths():
    repo_root = Path(__file__).resolve().parent.parent.parent

    # Old candidate 17-request collection should not be the active target
    old_collection = repo_root / "tests/postman/nodeskclaw_agent_acceptance.postman_collection.json"
    assert not old_collection.exists(), "Old candidate 17-request collection must be deleted"

    old_env = repo_root / "tests/postman/nodeskclaw_agent_acceptance.postman_environment.json"
    assert not old_env.exists(), "Direct non-template env file must not exist"

    old_sh = repo_root / "tests/postman/run_newman.sh"
    assert not old_sh.exists(), "Legacy bash runner must be deleted"

    old_fault_suite = repo_root / "tools/acceptance/fault_suite.py"
    assert not old_fault_suite.exists(), "Printing-only fault suite must be deleted"

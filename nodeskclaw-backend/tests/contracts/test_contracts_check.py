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
    assert (backend_root / "contracts/skill-run/v1.2.0/SHA256SUMS").exists()
    assert (backend_root / "contracts/skill-run/v1.2.0/events/run-event.schema.json").exists()


def test_skill_run_v10_contains_the_complete_public_consumer_surface():
    backend_root = Path(__file__).resolve().parents[2]
    root = backend_root / "contracts/skill-run/v1.0.0"
    expected_artifacts = {
        "mcp/tools-list.request.schema.json",
        "mcp/tools-list.response.schema.json",
        "mcp/tools-call.request.schema.json",
        "mcp/tools-call.response.schema.json",
        "runs/public-run.schema.json",
        "runs/result.schema.json",
        "runs/artifact-descriptor.schema.json",
        "runs/artifact-list.schema.json",
        "runs/artifact-download.response.schema.json",
        "events/run-event.schema.json",
        "http/endpoint-matrix.json",
        "fixtures/tools-call-accepted.json",
        "fixtures/run-cancelled.json",
        "fixtures/run-timeout.json",
        "fixtures/sse-resume-duplicate.json",
        "fixtures/artifact-with-checksum.json",
        "fixtures/auth-tenant-denial.json",
        "fixtures/idempotency-replay.json",
        "fixtures/unsupported-capabilities.json",
    }

    assert {path.relative_to(root).as_posix() for path in contracts_module._artifact_files(root)} >= expected_artifacts
    forbidden_artifacts = {
        "runs/run.schema.json",
        "runs/execution-snapshot.schema.json",
        "edge/artifact-upload.schema.json",
        "edge/lease-renew.schema.json",
        "installations/actual-report.schema.json",
        "installations/installation.schema.json",
    }
    assert not ({path.relative_to(root).as_posix() for path in contracts_module._artifact_files(root)} & forbidden_artifacts)


def test_skill_run_v10_public_fixtures_validate_against_their_contract_schemas():
    backend_root = Path(__file__).resolve().parents[2]

    contracts_module._validate_skill_run_fixtures(backend_root / "contracts/skill-run/v1.0.0")


from __future__ import annotations

import json
from pathlib import Path

from scripts import contracts as contracts_module


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REMOTE_ROOT = BACKEND_ROOT / "contracts/remote-agent/v1.0.0"
REMOTE_V11_ROOT = BACKEND_ROOT / "contracts/remote-agent/v1.1.0"
REMOTE_V12_ROOT = BACKEND_ROOT / "contracts/remote-agent/v1.2.0"
SKILL_V16_ROOT = BACKEND_ROOT / "contracts/skill-run/v1.6.0"


def test_remote_agent_bundle_checksums_match_manifest():
    contracts_module._validate_skill_run_checksums_exact(REMOTE_ROOT)


def test_skill_run_v16_bundle_remains_checksum_closed():
    contracts_module._validate_skill_run_checksums_exact(SKILL_V16_ROOT)


def test_remote_agent_release_marks_acp_unsupported():
    text = (REMOTE_ROOT / "RELEASE.md").read_text(encoding="utf-8")
    assert "ACP" in text
    assert "unsupported" in text.lower()


def test_remote_agent_create_schema_has_no_skill_identity():
    schema = json.loads((REMOTE_ROOT / "schemas/create.request.schema.json").read_text(encoding="utf-8"))
    assert schema["$id"] == "remote-agent.run.create.v1"
    assert "skill_id" not in schema["properties"]
    assert "capability_ref" not in schema["properties"]
    assert "tool_name" not in schema["properties"]


def test_remote_agent_v11_bundle_checksums_and_binding_field():
    contracts_module._validate_skill_run_checksums_exact(REMOTE_V11_ROOT)
    contracts_module._validate_skill_run_checksums_exact(REMOTE_ROOT)
    contracts_module._validate_skill_run_checksums_exact(SKILL_V16_ROOT)
    schema = json.loads((REMOTE_V11_ROOT / "schemas/create.request.schema.json").read_text(encoding="utf-8"))
    assert schema["$id"] == "remote-agent.run.create.v1.1"
    assert schema["additionalProperties"] is False
    assert "connector_binding_refs" in schema["properties"]
    assert "connector_binding_refs" not in schema["required"]
    frozen = json.loads((REMOTE_ROOT / "schemas/create.request.schema.json").read_text(encoding="utf-8"))
    assert "connector_binding_refs" not in frozen["properties"]
    release = (REMOTE_V11_ROOT / "RELEASE.md").read_text(encoding="utf-8")
    assert "ACP" in release
    assert "unsupported" in release.lower()
    assert "Composio" in release
    manifest = json.loads((REMOTE_V11_ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["contractVersion"] == "1.1.0"
    assert manifest["acp"] == "unsupported"


def test_remote_agent_schema_ids_cover_public_operations():
    manifest = json.loads((REMOTE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["acp"] == "unsupported"
    assert set(manifest["schemaIds"]) == {
        "remote-agent.run.create.v1",
        "remote-agent.run.get.v1",
        "remote-agent.run.events.v1",
        "remote-agent.run.result.v1",
        "remote-agent.run.artifacts.v1",
        "remote-agent.run.cancel.v1",
        "remote-agent.run.approval.v1",
    }


def test_remote_agent_v12_adds_account_refs_without_changing_older_bundles():
    contracts_module._validate_skill_run_checksums_exact(REMOTE_V12_ROOT)
    contracts_module._validate_skill_run_checksums_exact(REMOTE_V11_ROOT)
    contracts_module._validate_skill_run_checksums_exact(REMOTE_ROOT)
    schema = json.loads((REMOTE_V12_ROOT / "schemas/create.request.schema.json").read_text(encoding="utf-8"))
    assert schema["$id"] == "remote-agent.run.create.v1.2"
    assert schema["additionalProperties"] is False
    assert "integration_account_refs" in schema["properties"]
    assert "integration_account_refs" not in schema["required"]
    v11 = json.loads((REMOTE_V11_ROOT / "schemas/create.request.schema.json").read_text(encoding="utf-8"))
    assert "integration_account_refs" not in v11["properties"]

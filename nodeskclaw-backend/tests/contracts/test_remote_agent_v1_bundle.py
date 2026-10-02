from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from scripts import contracts as contracts_module


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REMOTE_ROOT = BACKEND_ROOT / "contracts/remote-agent/v1.0.0"
REMOTE_V11_ROOT = BACKEND_ROOT / "contracts/remote-agent/v1.1.0"
REMOTE_V12_ROOT = BACKEND_ROOT / "contracts/remote-agent/v1.2.0"
REMOTE_V13_ROOT = BACKEND_ROOT / "contracts/remote-agent/v1.3.0"
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
    manifest = json.loads((REMOTE_V12_ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["implementationHeadSha"] == "9d9085538fd1b0077cbd5a2056c5b07b9df795fa"
    assert manifest["releaseCommitSha"] != manifest["implementationHeadSha"]
    assert len(manifest["releaseCommitSha"]) == 40


def test_remote_agent_v13_adds_attachment_refs_without_changing_older_bundles():
    contracts_module._validate_skill_run_checksums_exact(REMOTE_V13_ROOT)
    contracts_module._validate_skill_run_checksums_exact(REMOTE_V12_ROOT)
    contracts_module._validate_skill_run_checksums_exact(REMOTE_V11_ROOT)
    contracts_module._validate_skill_run_checksums_exact(REMOTE_ROOT)
    contracts_module._validate_skill_run_checksums_exact(SKILL_V16_ROOT)
    schema = json.loads((REMOTE_V13_ROOT / "schemas/create.request.schema.json").read_text(encoding="utf-8"))
    assert schema["$id"] == "remote-agent.run.create.v1.3"
    assert schema["additionalProperties"] is False
    assert schema["properties"]["attachment_refs"]["uniqueItems"] is False
    v12 = json.loads((REMOTE_V12_ROOT / "schemas/create.request.schema.json").read_text(encoding="utf-8"))
    assert "attachment_refs" not in v12["properties"]
    manifest = json.loads((REMOTE_V13_ROOT / "manifest.json").read_text(encoding="utf-8"))
    sums = (REMOTE_V13_ROOT / "SHA256SUMS").read_text(encoding="utf-8")
    assert manifest["bundleDigest"] == contracts_module.bundle_digest_from_checksums(sums)
    release = (REMOTE_V13_ROOT / "RELEASE.md").read_text(encoding="utf-8")
    assert "POST /api/v1/attachments" in release
    assert "Work interface" in release


def test_attachment_live_runner_exits_nonzero_without_credentials():
    script = Path(__file__).resolve().parents[3] / "tools" / "acceptance" / "run_remote_agent_v13_attachment_live.py"
    env = {key: value for key, value in os.environ.items() if key not in {
        "NODESKCLAW_BACKEND_URL",
        "NODESKCLAW_AGENT_URL",
        "HERMES_URL",
        "NODESKCLAW_ATTACHMENT_TEST_ACCOUNT",
    }}
    completed = subprocess.run(
        [sys.executable, str(script)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
    body = json.loads(completed.stdout)
    assert body["production_gate"] == "unpassed"
    assert body["cases"] == [f"LIVE-ATT-{index:03d}" for index in range(1, 16)]

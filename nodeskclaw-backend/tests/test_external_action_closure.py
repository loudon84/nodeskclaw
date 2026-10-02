import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.external_action.composio_client import ComposioCallError
from app.services.external_action.execution_ledger import ledger_gate, provider_idempotency_key
from app.services.external_action.provider_port import ComposioExternalActionProvider
from app.services.external_action.scope import scope_digest
from app.services.external_action.session_broker import ExternalActionBroker
from app.services.integration_account_service import CONNECT_LINK_TTL_SECONDS, correlation_candidates
from scripts.contracts import bundle_digest_from_checksums


def test_correlation_uses_set_difference_not_the_first_active_account():
    assert correlation_candidates(["ca_old"], ["ca_old", "ca_new"]) == ["ca_new"]
    assert correlation_candidates(["ca_old"], ["ca_old"]) == []
    assert correlation_candidates(["ca_old"], ["ca_old", "ca_a", "ca_b"]) == ["ca_a", "ca_b"]
    assert CONNECT_LINK_TTL_SECONDS == 1800


def test_scope_digest_ignores_dict_order_and_session_material():
    left = scope_digest(
        {
            "provider": "composio",
            "provider_user_id": "nodeskclaw:org:user",
            "run_id": "run-1",
            "account_pins": [{"toolkit_slug": "gmail", "connected_account_id": "ca", "integration_account_id": "b"}],
            "toolkit_allowlist": ["gmail"],
            "tool_allowlist": ["ext__composio__gmail__search"],
        }
    )
    right = scope_digest(
        {
            "tool_allowlist": ["ext__composio__gmail__search"],
            "toolkit_allowlist": ["gmail"],
            "account_pins": [{"integration_account_id": "b", "connected_account_id": "ca", "toolkit_slug": "gmail"}],
            "run_id": "run-1",
            "provider_user_id": "nodeskclaw:org:user",
            "provider": "composio",
            "session_ref": "secret-session",
        }
    )
    assert left == right
    assert "secret-session" not in left


def test_idempotency_key_is_a_hash_of_the_canonical_array():
    key = provider_idempotency_key(
        run_id="run",
        attempt_id="att",
        generation=2,
        tool_call_id="call",
        arguments_digest="digest",
    )
    assert key == provider_idempotency_key(
        run_id="run",
        attempt_id="att",
        generation=2,
        tool_call_id="call",
        arguments_digest="digest",
    )
    raw = "runatt2calldigest"
    assert key != hashlib.sha256(raw.encode()).hexdigest()
    assert ledger_gate(None, None, "digest") == "start"
    assert ledger_gate("EXECUTING", "digest", "digest") == "unknown"
    assert ledger_gate("SUCCEEDED", "digest", "other") == "conflict"
    assert ledger_gate("SUCCEEDED", "digest", "digest") == "replay"


def test_live_runner_stays_unpassed_without_real_credentials():
    env = os.environ.copy()
    for name in (
        "NODESKCLAW_BACKEND_URL",
        "NODESKCLAW_AGENT_URL",
        "HERMES_URL",
        "COMPOSIO_API_KEY",
        "COMPOSIO_TEST_ACCOUNT",
    ):
        env.pop(name, None)
    script = Path(__file__).resolve().parents[2] / "tools" / "acceptance" / "run_remote_agent_v121_live.py"
    completed = subprocess.run([sys.executable, str(script)], env=env, capture_output=True, text=True, check=False)
    assert completed.returncode != 0
    body = json.loads(completed.stdout)
    assert body["SMC_ACCEPTANCE_RESULT"] == "FAIL"
    assert body["production_gate"] == "unpassed"
    assert body["cases"] == [f"LIVE-{index:03d}" for index in range(1, 21)]


def test_composio_adapter_does_not_claim_idempotency_or_inspection():
    provider = ComposioExternalActionProvider()
    assert provider.idempotency_support is False
    assert provider.supports_execution_inspection is False


def test_future_bundle_digest_excludes_manifest_and_frozen_bundles_stay_unchanged():
    text = "\n".join(
        [
            "bbb  b.json",
            "aaa  manifest.json",
            "ccc  a.json",
            "ddd  BUNDLE_DIGEST",
        ]
    )
    digest = bundle_digest_from_checksums(text)
    expected = hashlib.sha256(b"ccc  a.json\nbbb  b.json\n").hexdigest()
    assert digest == expected
    for relative in (
        "contracts/remote-agent/v1.2.0/manifest.json",
        "contracts/integration-account/v1.0.0/manifest.json",
        "contracts/remote-agent/v1.0.0/manifest.json",
        "contracts/remote-agent/v1.1.0/manifest.json",
    ):
        body = json.loads(Path(relative).read_text(encoding="utf-8"))
        assert "bundleDigest" not in body


@pytest.mark.asyncio
async def test_legacy_session_without_scope_digest_does_not_call_provider(monkeypatch):
    calls = {"count": 0}

    class Client:
        async def create_session(self, **kwargs):
            calls["count"] += 1
            return "new"

        async def execute(self, **kwargs):
            calls["count"] += 1
            return {}

        async def close_session(self, session_id):
            calls["count"] += 1

    class DB:
        async def commit(self):
            return None

    monkeypatch.setattr("app.services.external_action.session_broker.flag_modified", lambda *args, **kwargs: None)
    task = SimpleNamespace(routing_metadata={"provider_execution_session_ref": "legacy"})
    result = await ExternalActionBroker(DB(), client=Client()).execute(
        task=task,
        provider_user_id="nodeskclaw:org:user",
        connected_account_id="ca",
        toolkit_slug="gmail",
        provider_tool_key="GMAIL_SEARCH_EMAILS",
        arguments={},
        scope={
            "provider": "composio",
            "provider_user_id": "nodeskclaw:org:user",
            "run_id": "run-1",
            "account_pins": [{"integration_account_id": "acc", "toolkit_slug": "gmail", "connected_account_id": "ca"}],
            "toolkit_allowlist": ["gmail"],
            "tool_allowlist": ["ext__composio__gmail__search"],
        },
    )
    assert result["outcome"] == "fail_run"
    assert calls["count"] == 0


@pytest.mark.asyncio
async def test_matching_scope_digest_does_not_create_a_second_session(monkeypatch):
    calls = {"create": 0, "execute": 0}

    class Client:
        async def create_session(self, **kwargs):
            calls["create"] += 1
            raise ComposioCallError("tool_error", "must not create")

        async def execute(self, **kwargs):
            calls["execute"] += 1
            assert "idempotency" not in kwargs
            return {"data": "ok"}

        async def close_session(self, session_id):
            raise AssertionError("close")

    scope = {
        "provider": "composio",
        "provider_user_id": "nodeskclaw:org:user",
        "run_id": "run-1",
        "account_pins": [{"integration_account_id": "acc", "toolkit_slug": "gmail", "connected_account_id": "ca"}],
        "toolkit_allowlist": ["gmail"],
        "tool_allowlist": ["ext__composio__gmail__search"],
    }
    monkeypatch.setattr("app.services.external_action.session_broker.flag_modified", lambda *args, **kwargs: None)
    task = SimpleNamespace(
        routing_metadata={
            "provider_execution_session_ref": "session-1",
            "provider_execution_scope_digest": scope_digest(scope),
        }
    )
    result = await ExternalActionBroker(SimpleNamespace(), client=Client()).execute(
        task=task,
        provider_user_id="nodeskclaw:org:user",
        connected_account_id="ca",
        toolkit_slug="gmail",
        provider_tool_key="GMAIL_SEARCH_EMAILS",
        arguments={"q": "hello"},
        scope=scope,
    )
    assert result["outcome"] == "ok"
    assert calls["create"] == 0
    assert calls["execute"] == 1

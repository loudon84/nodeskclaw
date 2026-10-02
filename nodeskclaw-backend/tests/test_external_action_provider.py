from types import SimpleNamespace

import pytest

from app.services.expert_external_action_policy_service import require_toolkit_coverage
from app.services.external_action.naming import has_surface_collision, surface_name, surface_names_for_accounts
from app.services.external_action.session_broker import ExternalActionBroker
from app.services.external_action.composio_client import ComposioCallError
from app.services.integration_account_service import external_descriptors, load_accounts_for_run
from app.services.remote_agent_provider_service import (
    RemoteAgentProviderService,
    RemoteAgentRouteError,
    parse_create_body,
    request_digest,
)


def test_surface_name_normalizes_and_detects_collision():
    assert surface_name("composio", "Gmail", "GMAIL_SEARCH_EMAILS") == "ext__composio__gmail__gmail_search_emails"
    names = surface_names_for_accounts(
        [("composio", "gmail"), ("composio", "gmail")],
        [("composio", "gmail", "GMAIL_SEARCH_EMAILS")],
    )
    assert has_surface_collision(names, [])
    distinct = surface_names_for_accounts(
        [("composio", "gmail")],
        [("composio", "gmail", "GMAIL_SEARCH_EMAILS")],
    )
    assert has_surface_collision(distinct, ["ext__composio__gmail__gmail_search_emails"])
    assert not has_surface_collision(distinct, ["crm.lookup"])


def test_account_refs_change_digest_without_versions():
    base = request_digest(agent_ref="expert", prompt="hello", knowledge_refs=[], session_ref=None)
    ordered = request_digest(
        agent_ref="expert",
        prompt="hello",
        knowledge_refs=[],
        integration_account_refs=[
            "22222222-2222-4222-8222-222222222222",
            "11111111-1111-4111-8111-111111111111",
        ],
        session_ref=None,
    )
    resorted = request_digest(
        agent_ref="expert",
        prompt="hello",
        knowledge_refs=[],
        integration_account_refs=[
            "11111111-1111-4111-8111-111111111111",
            "22222222-2222-4222-8222-222222222222",
        ],
        session_ref=None,
    )
    assert ordered == resorted
    assert ordered != base


def test_non_uuid_account_ref_is_context_rejected():
    with pytest.raises(RemoteAgentRouteError) as exc:
        parse_create_body({
            "client_request_id": "req-1",
            "agent_ref": "expert",
            "prompt": "hello",
            "integration_account_refs": ["not-a-uuid"],
        })
    assert exc.value.symbol == "REMOTE_AGENT_CONTEXT_REJECTED"
    assert exc.value.code == 40004


class _AccountDB:
    def __init__(self, row):
        self.row = row

    async def get(self, model, account_id):
        if self.row is not None and account_id == self.row.id:
            return self.row
        return None


def _row(**overrides):
    base = dict(
        id="11111111-1111-4111-8111-111111111111",
        deleted_at=None,
        org_id="org",
        user_id="user",
        status="ACTIVE",
        provider="composio",
        toolkit_slug="gmail",
        connected_account_id="ca_1",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_inactive_and_deleted_accounts_use_distinct_codes():
    with pytest.raises(RemoteAgentRouteError) as inactive:
        await load_accounts_for_run(
            _AccountDB(_row(status="DISCONNECTED")),
            org_id="org",
            user_id="user",
            account_ids=["11111111-1111-4111-8111-111111111111"],
        )
    assert inactive.value.code == 40908
    with pytest.raises(RemoteAgentRouteError) as missing:
        await load_accounts_for_run(
            _AccountDB(_row(deleted_at="2026-10-02")),
            org_id="org",
            user_id="user",
            account_ids=["11111111-1111-4111-8111-111111111111"],
        )
    assert missing.value.code == 40404
    with pytest.raises(RemoteAgentRouteError) as other_user:
        await load_accounts_for_run(
            _AccountDB(_row(user_id="other")),
            org_id="org",
            user_id="user",
            account_ids=["11111111-1111-4111-8111-111111111111"],
        )
    assert other_user.value.code == 40404


def test_descriptor_whitelist_omits_versions_and_secrets():
    body = external_descriptors([_row()])[0]
    assert set(body) == {
        "integration_account_id",
        "provider",
        "toolkit_slug",
        "connected_account_ref",
    }


def test_missing_toolkit_policy_is_scope_denied():
    with pytest.raises(RemoteAgentRouteError) as exc:
        require_toolkit_coverage([_row()], [])
    assert exc.value.code == 40303


@pytest.mark.asyncio
async def test_session_create_failure_does_not_execute(monkeypatch):
    calls = {"execute": 0}

    class Client:
        async def create_session(self, **kwargs):
            raise ComposioCallError("tool_error", "down")

        async def execute(self, **kwargs):
            calls["execute"] += 1
            return {}

    monkeypatch.setattr("app.services.external_action.session_broker.flag_modified", lambda *args, **kwargs: None)
    task = SimpleNamespace(routing_metadata={})
    result = await ExternalActionBroker(SimpleNamespace(), client=Client()).execute(
        task=task,
        provider_user_id="nodeskclaw:org:user",
        connected_account_id="ca_1",
        toolkit_slug="gmail",
        provider_tool_key="GMAIL_SEARCH_EMAILS",
        arguments={},
    )
    assert result["outcome"] == "tool_error"
    assert calls["execute"] == 0


@pytest.mark.asyncio
async def test_digest_replay_skips_account_checks(monkeypatch):
    digest = request_digest(
        agent_ref="expert",
        prompt="hello",
        knowledge_refs=[],
        integration_account_refs=["11111111-1111-4111-8111-111111111111"],
        session_ref=None,
    )
    existing = SimpleNamespace(routing_metadata={"request_digest": digest})

    class Tasks:
        def __init__(self, db):
            return None

        async def find_idempotent_task(self, *args, **kwargs):
            return existing

    class Boom:
        def __init__(self, db):
            raise AssertionError("later checks must not run on replay")

    monkeypatch.setattr("app.services.remote_agent_provider_service.TaskService", Tasks)
    monkeypatch.setattr("app.services.remote_agent_provider_service.ExpertCatalogService", Boom)
    monkeypatch.setattr("app.services.remote_agent_provider_service.RuntimeSkillRunService", Boom)
    task, replayed = await RemoteAgentProviderService(SimpleNamespace()).create(
        org_id="org",
        user_id="user",
        payload={
            "client_request_id": "req-1",
            "agent_ref": "expert",
            "prompt": "hello",
            "integration_account_refs": ["11111111-1111-4111-8111-111111111111"],
        },
    )
    assert replayed is True
    assert task is existing

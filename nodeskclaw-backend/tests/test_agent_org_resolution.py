from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import trust
from app.core.deps import get_current_org_or_agent
from app.core.security import AuthActor, _auth_actor


class _ScalarResult:
    def __init__(self, value) -> None:
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _SequenceDb:
    def __init__(self, results: list) -> None:
        self._results = list(results)
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        if not self._results:
            raise AssertionError("unexpected database execute")
        return self._results.pop(0)


def _compiled_param_values(stmt) -> set:
    return set(stmt.compile().params.values())


@pytest.fixture
def agent_actor():
    token = _auth_actor.set(AuthActor("agent", "inst-1", "Hermes"))
    try:
        yield
    finally:
        _auth_actor.reset(token)


@pytest.fixture
def user_actor():
    token = _auth_actor.set(AuthActor("user", "user-1", "Alice"))
    try:
        yield
    finally:
        _auth_actor.reset(token)


async def test_agent_org_resolution_uses_instance_org(agent_actor):
    user = SimpleNamespace(id="user-1", current_org_id="org-other")
    instance = SimpleNamespace(id="inst-1", org_id="org-instance")
    org = SimpleNamespace(id="org-instance")
    db = _SequenceDb([_ScalarResult(instance), _ScalarResult(org)])

    resolved_user, resolved_org = await get_current_org_or_agent(db=db, user=user)

    assert resolved_user is user
    assert resolved_org.id == "org-instance"
    assert len(db.statements) == 2


async def test_agent_org_resolution_allows_legacy_instance_without_org(agent_actor):
    user = SimpleNamespace(id="user-1", current_org_id="org-other")
    instance = SimpleNamespace(id="inst-1", org_id=None)
    db = _SequenceDb([_ScalarResult(instance)])

    _resolved_user, resolved_org = await get_current_org_or_agent(db=db, user=user)

    assert resolved_org.id is None
    assert len(db.statements) == 1


async def test_agent_org_resolution_rejects_missing_actor_instance(agent_actor):
    user = SimpleNamespace(id="user-1", current_org_id="org-other")
    db = _SequenceDb([_ScalarResult(None)])

    with pytest.raises(HTTPException) as exc:
        await get_current_org_or_agent(db=db, user=user)

    assert exc.value.status_code == 401
    assert exc.value.detail["message_key"] == "errors.auth.token_invalid"


async def test_user_org_resolution_keeps_provider_path(monkeypatch, user_actor):
    user = SimpleNamespace(id="user-1", current_org_id="org-user")
    org = SimpleNamespace(id="org-user")
    db = _SequenceDb([])

    class _Provider:
        async def resolve_org_for_user(self, resolved_user, resolved_db):
            assert resolved_user is user
            assert resolved_db is db
            return org

    monkeypatch.setattr("app.services.org.factory.get_org_provider", lambda: _Provider())

    _resolved_user, resolved_org = await get_current_org_or_agent(db=db, user=user)

    assert resolved_org is org
    assert db.statements == []


async def test_agent_trust_check_uses_instance_org_not_creator_current_org(agent_actor):
    user = SimpleNamespace(id="user-1", current_org_id="org-other")
    instance = SimpleNamespace(id="inst-1", org_id="org-instance")
    org = SimpleNamespace(id="org-instance")
    workspace = SimpleNamespace(id="ws-1")
    policy = SimpleNamespace(id="policy-1")
    db = _SequenceDb([
        _ScalarResult(instance),
        _ScalarResult(org),
        _ScalarResult(workspace),
        _ScalarResult("workspace-agent-1"),
        _ScalarResult(policy),
    ])

    org_ctx = await get_current_org_or_agent(db=db, user=user)
    response = await trust.check_trust("ws-1", "inst-1", "deploy", org_ctx=org_ctx, db=db)

    assert response == {"code": 0, "message": "success", "data": {"trusted": True}}
    workspace_query_params = _compiled_param_values(db.statements[2])
    assert "org-instance" in workspace_query_params
    assert "org-other" not in workspace_query_params


async def test_agent_trust_check_still_requires_workspace_membership(agent_actor):
    user = SimpleNamespace(id="user-1", current_org_id="org-other")
    instance = SimpleNamespace(id="inst-1", org_id="org-instance")
    org = SimpleNamespace(id="org-instance")
    workspace = SimpleNamespace(id="ws-1")
    db = _SequenceDb([
        _ScalarResult(instance),
        _ScalarResult(org),
        _ScalarResult(workspace),
        _ScalarResult(None),
    ])

    org_ctx = await get_current_org_or_agent(db=db, user=user)
    with pytest.raises(HTTPException) as exc:
        await trust.check_trust("ws-1", "inst-1", "deploy", org_ctx=org_ctx, db=db)

    assert exc.value.status_code == 403
    assert exc.value.detail["message_key"] == "errors.workspace.agent_not_in_workspace"

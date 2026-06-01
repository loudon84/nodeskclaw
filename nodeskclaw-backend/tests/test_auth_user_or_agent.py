from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core import security


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


@pytest.fixture(autouse=True)
def reset_auth_actor():
    token = security._auth_actor.set(None)
    try:
        yield
    finally:
        security._auth_actor.reset(token)


def _credentials(token: str = "token") -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.mark.asyncio
async def test_user_or_agent_rejects_password_change_required_user_token(monkeypatch):
    user = SimpleNamespace(id="user-1", name="Alice", must_change_password=True)
    db = SimpleNamespace()

    async def fake_get_user_by_token(token, resolved_db):
        assert token == "jwt-token"
        assert resolved_db is db
        return user

    monkeypatch.setattr(security, "_get_user_by_token", fake_get_user_by_token)

    with pytest.raises(HTTPException) as exc:
        await security.get_current_user_or_agent(credentials=_credentials("jwt-token"), db=db)

    assert exc.value.status_code == 403
    assert exc.value.detail["message_key"] == "errors.auth.password_change_required"


@pytest.mark.asyncio
async def test_user_or_agent_agent_token_ignores_creator_password_change(monkeypatch):
    creator = SimpleNamespace(id="user-1", name="Alice", must_change_password=True)
    instance = SimpleNamespace(id="inst-1", name="Hermes", created_by="user-1")
    db = _SequenceDb([_ScalarResult(instance), _ScalarResult(creator)])

    async def fake_get_user_by_token(token, resolved_db):
        assert token == "proxy-token"
        assert resolved_db is db
        raise HTTPException(status_code=401, detail={"message_key": "errors.auth.token_invalid"})

    monkeypatch.setattr(security, "_get_user_by_token", fake_get_user_by_token)

    resolved_user = await security.get_current_user_or_agent(
        credentials=_credentials("proxy-token"),
        db=db,
    )

    actor = security.get_auth_actor()
    assert resolved_user is creator
    assert actor is not None
    assert actor.actor_type == "agent"
    assert actor.actor_id == "inst-1"
    assert len(db.statements) == 2

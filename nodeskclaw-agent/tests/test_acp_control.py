from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.acp_gateway.session import session_has_nonterminal_run


@pytest.mark.asyncio
async def test_cancel_uses_run_service(monkeypatch):
    from app.acp_gateway.connection import AcpConnection
    from app.services import run_service

    cancelled = {}

    async def fake_cancel(db, run_id, *, org_id):
        cancelled["run_id"] = run_id
        cancelled["org_id"] = org_id
        return SimpleNamespace(status="CANCELLING")

    monkeypatch.setattr(run_service, "cancel_run", fake_cancel)

    class DummyWs:
        pass

    conn = AcpConnection(DummyWs(), AsyncMock(), {"org_id": "org", "user_id": "user", "agent_ref": "a"}, "cap")

    async def fake_require(params):
        return "sess", {}

    async def fake_latest(db, session_id):
        return {"id": "run-9"}

    monkeypatch.setattr(conn, "_require_session", fake_require)
    monkeypatch.setattr("app.acp_gateway.connection.latest_run_for_session", fake_latest)
    await conn._session_cancel({"sessionId": "sess"})
    assert cancelled == {"run_id": "run-9", "org_id": "org"}


@pytest.mark.asyncio
async def test_session_busy_query_uses_nonterminal():
    db = AsyncMock()
    result = AsyncMock()
    result.first = lambda: ("run-1",)
    db.execute = AsyncMock(return_value=result)
    assert await session_has_nonterminal_run(db, "sess") is True

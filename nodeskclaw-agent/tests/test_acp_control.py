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
async def test_prompt_commits_before_event_pump(monkeypatch):
    from app.acp_gateway.connection import AcpConnection

    order: list[str] = []
    db = AsyncMock()

    async def fake_commit():
        order.append("commit")

    db.commit = fake_commit
    conn = AcpConnection(AsyncMock(), db, {"org_id": "o", "user_id": "u", "agent_ref": "a"}, "cap")

    async def fake_require(params):
        return "sess", {}

    async def fake_create(*args, **kwargs):
        order.append("create")
        return {"run_id": "run-1", "replay": False}

    async def fake_pump(*args, **kwargs):
        order.append("pump")
        return "end_turn"

    monkeypatch.setattr(conn, "_require_session", fake_require)
    monkeypatch.setattr("app.acp_gateway.connection.create_or_replay_prompt_run", fake_create)
    monkeypatch.setattr("app.acp_gateway.connection.pump_run_events", fake_pump)
    result = await conn._session_prompt("11111111-1111-1111-1111-111111111111", {"sessionId": "sess", "prompt": []})
    assert result == {"stopReason": "end_turn"}
    assert order == ["create", "commit", "pump"]


@pytest.mark.asyncio
async def test_serve_accepts_cancel_while_prompt_runs(monkeypatch):
    import asyncio
    import json

    from app.acp_gateway.connection import AcpConnection

    started = asyncio.Event()
    released = asyncio.Event()
    frames = [
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "11111111-1111-1111-1111-111111111111",
                "method": "session/prompt",
                "params": {"sessionId": "sess", "prompt": [{"type": "text", "text": "hi"}]},
            }
        ),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "22222222-2222-2222-2222-222222222222",
                "method": "session/cancel",
                "params": {"sessionId": "sess"},
            }
        ),
    ]

    class DummyWs:
        def __init__(self):
            self.sent = []

        async def receive_text(self):
            if not frames:
                await released.wait()
                raise asyncio.CancelledError
            return frames.pop(0)

        async def send_text(self, payload):
            self.sent.append(payload)

    db = AsyncMock()
    db.commit = AsyncMock()
    conn = AcpConnection(DummyWs(), db, {"org_id": "o", "user_id": "u", "agent_ref": "a"}, "cap")
    conn.initialized = True
    cancelled = {}

    async def fake_prompt(request_id, params):
        started.set()
        await released.wait()
        return {"stopReason": "cancelled"}

    async def fake_cancel(params):
        cancelled["ok"] = True
        released.set()

    monkeypatch.setattr(conn, "_session_prompt", fake_prompt)
    monkeypatch.setattr(conn, "_session_cancel", fake_cancel)
    task = asyncio.create_task(conn.serve())
    await asyncio.wait_for(started.wait(), timeout=1)
    await asyncio.sleep(0.05)
    assert cancelled.get("ok") is True
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass


@pytest.mark.asyncio
async def test_session_busy_query_uses_nonterminal():
    db = AsyncMock()
    result = AsyncMock()
    result.first = lambda: ("run-1",)
    db.execute = AsyncMock(return_value=result)
    assert await session_has_nonterminal_run(db, "sess") is True

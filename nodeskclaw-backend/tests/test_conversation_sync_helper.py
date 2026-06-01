import pytest

from app.services import conversation_service
from app.services.runtime.pg_notify import PGNotifyService


@pytest.mark.asyncio
async def test_sync_conversations_and_notify_topology_runs_sync_before_notify(monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []

    async def fake_sync(workspace_id, db):
        calls.append(f"sync:{workspace_id}")
        return ["conversation"]

    async def fake_notify(db, workspace_id):
        calls.append(f"notify:{workspace_id}")

    monkeypatch.setattr(conversation_service, "sync_conversations_from_topology", fake_sync)
    monkeypatch.setattr(PGNotifyService, "notify_topology_changed", fake_notify)

    result = await conversation_service.sync_conversations_and_notify_topology("ws-helper", object())

    assert result == ["conversation"]
    assert calls == ["sync:ws-helper", "notify:ws-helper"]

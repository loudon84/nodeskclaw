from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import collaboration_service
from app.services import conversation_service
from app.services.runtime.messaging import bus as message_bus_module


class _FakeDb:
    def __init__(self) -> None:
        self.commit = AsyncMock()


def _session_factory(db: _FakeDb):
    @asynccontextmanager
    async def _factory():
        yield db

    return _factory


def _patch_common(monkeypatch: pytest.MonkeyPatch, db: _FakeDb):
    monkeypatch.setattr(collaboration_service, "async_session_factory", _session_factory(db))
    monkeypatch.setattr(
        collaboration_service.msg_service,
        "get_collaboration_depth_limit",
        AsyncMock(return_value=5),
    )
    monkeypatch.setattr(
        collaboration_service,
        "_get_instance",
        AsyncMock(return_value=SimpleNamespace(agent_display_name="Hermes", name="hermes")),
    )
    monkeypatch.setattr(
        collaboration_service.msg_service,
        "record_message",
        AsyncMock(return_value=SimpleNamespace(id="msg-1")),
    )
    publish = AsyncMock(return_value=SimpleNamespace(error=None))
    monkeypatch.setattr(message_bus_module.message_bus, "publish", publish)
    events: list[tuple[str, str, dict]] = []
    monkeypatch.setattr(
        "app.api.workspaces.broadcast_event",
        lambda workspace_id, event_type, payload: events.append((workspace_id, event_type, payload)),
    )
    return publish, events


@pytest.mark.asyncio
async def test_broadcast_collaboration_records_blackboard_conversation(monkeypatch: pytest.MonkeyPatch):
    db = _FakeDb()
    publish, events = _patch_common(monkeypatch, db)
    sync_conversations = AsyncMock()
    get_members = AsyncMock(return_value=["inst-1", "inst-2"])
    monkeypatch.setattr(
        conversation_service,
        "get_blackboard_conversation",
        AsyncMock(return_value=SimpleNamespace(id="conv-blackboard")),
    )
    monkeypatch.setattr(conversation_service, "sync_conversations_from_topology", sync_conversations)
    monkeypatch.setattr(conversation_service, "get_conversation_members", get_members)

    await collaboration_service.handle_collaboration_message(
        workspace_id="ws-1",
        source_instance_id="inst-1",
        target="broadcast",
        text="daily report",
        depth=1,
    )

    collaboration_service.msg_service.record_message.assert_awaited_once()
    assert collaboration_service.msg_service.record_message.await_args.kwargs["conversation_id"] == (
        "conv-blackboard"
    )
    assert events == [
        (
            "ws-1",
            "agent:collaboration",
            {
                "instance_id": "inst-1",
                "agent_name": "Hermes",
                "target": "broadcast",
                "content": "daily report",
                "conversation_id": "conv-blackboard",
            },
        )
    ]
    publish.assert_awaited_once()
    envelope = publish.await_args.args[0]
    assert envelope.data.routing.mode == "broadcast"
    assert envelope.data.routing.targets == []
    assert envelope.data.extensions["conversation_id"] == "conv-blackboard"
    sync_conversations.assert_not_awaited()
    get_members.assert_not_awaited()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_broadcast_collaboration_syncs_topology_when_blackboard_missing(
    monkeypatch: pytest.MonkeyPatch,
):
    db = _FakeDb()
    _patch_common(monkeypatch, db)
    sync_conversations = AsyncMock()
    monkeypatch.setattr(
        conversation_service,
        "get_blackboard_conversation",
        AsyncMock(side_effect=[None, SimpleNamespace(id="conv-after-sync")]),
    )
    monkeypatch.setattr(conversation_service, "sync_conversations_from_topology", sync_conversations)
    monkeypatch.setattr(conversation_service, "get_conversation_members", AsyncMock())

    await collaboration_service.handle_collaboration_message(
        workspace_id="ws-1",
        source_instance_id="inst-1",
        target="broadcast",
        text="daily report",
        depth=1,
    )

    sync_conversations.assert_awaited_once_with("ws-1", db)
    assert collaboration_service.msg_service.record_message.await_args.kwargs["conversation_id"] == (
        "conv-after-sync"
    )


@pytest.mark.asyncio
async def test_broadcast_collaboration_falls_back_when_blackboard_still_missing(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    db = _FakeDb()
    publish, events = _patch_common(monkeypatch, db)
    monkeypatch.setattr(
        conversation_service,
        "get_blackboard_conversation",
        AsyncMock(side_effect=[None, None]),
    )
    monkeypatch.setattr(conversation_service, "sync_conversations_from_topology", AsyncMock())
    monkeypatch.setattr(conversation_service, "get_conversation_members", AsyncMock())

    await collaboration_service.handle_collaboration_message(
        workspace_id="ws-1",
        source_instance_id="inst-1",
        target="broadcast",
        text="daily report",
        depth=1,
    )

    assert "Broadcast collaboration has no blackboard conversation in workspace ws-1" in caplog.text
    assert collaboration_service.msg_service.record_message.await_args.kwargs["conversation_id"] is None
    assert events[0][2]["conversation_id"] is None
    envelope = publish.await_args.args[0]
    assert "conversation_id" not in envelope.data.extensions
    assert envelope.data.routing.mode == "broadcast"

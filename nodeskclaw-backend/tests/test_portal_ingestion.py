from app.services.runtime.messaging.ingestion.portal import build_portal_envelope
from app.services.runtime.messaging.envelope import MessageEnvelope


def test_build_portal_envelope_promotes_mentions_to_routing_targets() -> None:
    envelope = build_portal_envelope(
        workspace_id="ws-1",
        user_id="user-1",
        user_name="Admin",
        content="hello",
        mentions=["agent-1"],
    )

    assert envelope.data is not None
    assert envelope.data.mentions == ["agent-1"]
    assert envelope.data.routing.mode == "unicast"
    assert envelope.data.routing.targets == ["agent-1"]
    assert envelope.data.extensions["mention_targets"] == ["agent-1"]


def test_build_portal_envelope_preserves_everyone_as_broadcast() -> None:
    envelope = build_portal_envelope(
        workspace_id="ws-1",
        user_id="user-1",
        user_name="Admin",
        content="hello everyone",
        mentions=["__all__"],
    )

    assert envelope.data is not None
    assert envelope.data.mentions == ["__all__"]
    assert envelope.data.extensions["mention_targets"] == ["__all__"]
    assert envelope.data.routing.mode == "multicast"
    assert envelope.data.routing.targets == []


def test_build_portal_envelope_defaults_to_multicast_without_mentions() -> None:
    envelope = build_portal_envelope(
        workspace_id="ws-1",
        user_id="user-1",
        user_name="Admin",
        content="hello",
    )

    assert envelope.data is not None
    assert envelope.data.routing.mode == "multicast"
    assert envelope.data.routing.targets == []


def test_build_portal_envelope_preserves_file_references() -> None:
    file_references = [{
        "source": "shared_file",
        "file_id": "file-1",
        "display_name": "brief.pdf",
        "size": 1024,
        "content_type": "application/pdf",
    }]

    envelope = build_portal_envelope(
        workspace_id="ws-1",
        user_id="user-1",
        user_name="Admin",
        content="看这个文件",
        file_references=file_references,
        message_id="msg-1",
    )
    restored = MessageEnvelope.from_dict(envelope.to_dict())

    assert restored.data is not None
    assert restored.data.file_references == file_references
    assert restored.data.extensions["message_id"] == "msg-1"

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas import ArtifactDescriptor
from app.services.hermes_engine import (
    ARTIFACT_PERSIST_FAILED,
    _collect_output_refs,
    _output_url_access,
    _persist_declared_outputs,
)
from app.services import run_service


async def _public_example_ips(host: str, port: int) -> list[str]:
    return ["93.184.216.34"]


def _mock_session(monkeypatch) -> None:
    session_cm = AsyncMock()
    session_cm.__aenter__.return_value = AsyncMock()
    session_cm.__aexit__.return_value = False
    monkeypatch.setattr("app.db.SessionLocal", lambda: session_cm)


def test_public_artifact_persisted_event_matches_store_append_shape():
    descriptor = ArtifactDescriptor(
        artifact_id="art-9",
        name="out.pdf",
        content_type="application/pdf",
        size_bytes=12,
        download_url="/api/v1/runs/run-1/artifacts/art-9/download",
        checksum_sha256="deadbeef",
        storage_state="persisted",
    )
    event = run_service.public_artifact_persisted_event(descriptor)
    assert event["event_type"] == "artifact.persisted"
    assert event["source"] == "agent"
    assert event["source_event_id"] == run_service.artifact_persisted_source_event_id("art-9")
    assert event["payload"] == {
        "artifact_id": "art-9",
        "name": "out.pdf",
        "content_type": "application/pdf",
        "size": 12,
        "checksum_sha256": "deadbeef",
    }
    assert "download_url" not in event["payload"]
    assert event["payload"] == run_service.artifact_persisted_payload(descriptor)


def test_collect_output_refs_ignores_markdown_guess():
    assert _collect_output_refs({"output": "see [report](https://example.com/out.pdf) at /tmp/out.pdf"}) == []
    assert _collect_output_refs({"final_response": "wrote out.pdf"}) == []
    refs = _collect_output_refs(
        {
            "output_refs": [
                {
                    "url": "https://example.com/out.pdf",
                    "name": "out.pdf",
                    "required": True,
                    "content_type": "application/pdf",
                }
            ]
        }
    )
    assert len(refs) == 1
    assert refs[0]["name"] == "out.pdf"


@pytest.mark.asyncio
async def test_persist_declared_outputs_uses_store_artifact_bytes(monkeypatch):
    descriptor = ArtifactDescriptor(
        artifact_id="art-1",
        name="out.pdf",
        content_type="application/pdf",
        size_bytes=5,
        checksum_sha256="abc",
        storage_state="persisted",
    )
    store = AsyncMock(return_value=descriptor)
    monkeypatch.setattr("app.services.run_service.store_artifact_bytes", store)
    monkeypatch.setattr("app.services.hermes_engine._resolve_output_host_ips", _public_example_ips)
    db = AsyncMock()
    session_cm = AsyncMock()
    session_cm.__aenter__.return_value = db
    session_cm.__aexit__.return_value = False
    monkeypatch.setattr("app.db.SessionLocal", lambda: session_cm)
    client = MagicMock()
    response = MagicMock()
    response.content = b"hello"
    response.raise_for_status = MagicMock()
    client.get = AsyncMock(return_value=response)

    events, failed = await _persist_declared_outputs(
        client,
        data={
            "output_refs": [
                {
                    "url": "https://example.com/out.pdf",
                    "name": "out.pdf",
                    "required": True,
                    "content_type": "application/pdf",
                }
            ]
        },
        headers={"Authorization": "Bearer example", "Content-Type": "application/json"},
        org_id="org-1",
        run_id="run-1",
        attempt_id="att-1",
        gateway_url="http://hermes:8642",
    )
    assert failed is False
    store.assert_awaited()
    assert store.await_args.kwargs["name"] == "out.pdf"
    assert store.await_args.kwargs["content"] == b"hello"
    assert events[0] == run_service.public_artifact_persisted_event(descriptor)
    assert "download_url" not in events[0]["payload"]
    client.get.assert_awaited_once()
    assert client.get.await_args.kwargs["headers"].get("Authorization") is None
    assert client.get.await_args.kwargs["headers"]["Content-Type"] == "application/json"
    db.commit.assert_awaited()
    db.rollback.assert_not_called()


@pytest.mark.asyncio
async def test_required_output_missing_http_ref_sets_artifact_persist_failed(monkeypatch):
    store = AsyncMock()
    monkeypatch.setattr("app.services.run_service.store_artifact_bytes", store)
    session_cm = AsyncMock()
    session_cm.__aenter__.return_value = AsyncMock()
    session_cm.__aexit__.return_value = False
    monkeypatch.setattr("app.db.SessionLocal", lambda: session_cm)
    client = MagicMock()
    client.get = AsyncMock()
    events, failed = await _persist_declared_outputs(
        client,
        data={"output_refs": [{"name": "/tmp/secret.bin", "required": True}]},
        headers={},
        org_id="org-1",
        run_id="run-1",
        attempt_id="att-1",
    )
    assert events == []
    assert failed is True
    store.assert_not_called()
    client.get.assert_not_called()


@pytest.mark.asyncio
async def test_optional_output_failure_has_no_fake_card(monkeypatch):
    store = AsyncMock(side_effect=RuntimeError("store down"))
    monkeypatch.setattr("app.services.run_service.store_artifact_bytes", store)
    monkeypatch.setattr("app.services.hermes_engine._resolve_output_host_ips", _public_example_ips)
    _mock_session(monkeypatch)
    client = MagicMock()
    response = MagicMock()
    response.content = b"x"
    response.raise_for_status = MagicMock()
    client.get = AsyncMock(return_value=response)
    events, failed = await _persist_declared_outputs(
        client,
        data={
            "output_refs": [
                {
                    "url": "https://example.com/optional.txt",
                    "name": "optional.txt",
                    "required": False,
                }
            ]
        },
        headers={"Authorization": "Bearer example"},
        org_id="org-1",
        run_id="run-1",
        attempt_id="att-1",
        gateway_url="http://hermes:8642",
    )
    assert failed is False
    assert events == []


@pytest.mark.asyncio
async def test_output_url_access_blocks_metadata_and_private_non_gateway():
    assert await _output_url_access("http://169.254.169.254/latest/meta-data", "http://hermes:8642") == "blocked"
    assert await _output_url_access("http://metadata.google.internal/", "http://hermes:8642") == "blocked"
    assert await _output_url_access("http://192.168.1.10/secret", "http://hermes:8642") == "blocked"
    assert await _output_url_access("http://127.0.0.1:9000/out", "http://hermes:8642") == "blocked"
    assert await _output_url_access("http://hermes:8642/outputs/a.pdf", "http://hermes:8642") == "gateway"
    assert await _output_url_access("http://192.168.1.10:8642/outputs/a.pdf", "http://192.168.1.10:8642") == "gateway"


@pytest.mark.asyncio
async def test_output_url_access_public_hostname_without_private_resolution(monkeypatch):
    monkeypatch.setattr("app.services.hermes_engine._resolve_output_host_ips", _public_example_ips)
    assert await _output_url_access("https://example.com/out.pdf", "http://hermes:8642") == "public"

    async def private_alias(host: str, port: int) -> list[str]:
        return ["10.0.0.8"]

    monkeypatch.setattr("app.services.hermes_engine._resolve_output_host_ips", private_alias)
    assert await _output_url_access("https://example.com/out.pdf", "http://hermes:8642") == "blocked"


@pytest.mark.asyncio
async def test_persist_gateway_same_origin_sends_authorization(monkeypatch):
    descriptor = ArtifactDescriptor(
        artifact_id="art-gw",
        name="a.pdf",
        content_type="application/pdf",
        size_bytes=3,
        checksum_sha256="abc",
        storage_state="persisted",
    )
    store = AsyncMock(return_value=descriptor)
    monkeypatch.setattr("app.services.run_service.store_artifact_bytes", store)
    _mock_session(monkeypatch)
    client = MagicMock()
    response = MagicMock()
    response.content = b"pdf"
    response.raise_for_status = MagicMock()
    client.get = AsyncMock(return_value=response)
    events, failed = await _persist_declared_outputs(
        client,
        data={
            "output_refs": [
                {
                    "url": "http://hermes:8642/v1/runs/r1/outputs/a.pdf",
                    "name": "a.pdf",
                    "required": True,
                }
            ]
        },
        headers={"Authorization": "Bearer lease-token"},
        org_id="org-1",
        run_id="run-1",
        attempt_id="att-1",
        gateway_url="http://hermes:8642",
    )
    assert failed is False
    assert events[0]["payload"]["artifact_id"] == "art-gw"
    client.get.assert_awaited_once()
    assert client.get.await_args.kwargs["headers"]["Authorization"] == "Bearer lease-token"


@pytest.mark.asyncio
async def test_persist_metadata_url_does_not_fetch(monkeypatch):
    store = AsyncMock()
    monkeypatch.setattr("app.services.run_service.store_artifact_bytes", store)
    _mock_session(monkeypatch)
    client = MagicMock()
    client.get = AsyncMock()
    events, failed = await _persist_declared_outputs(
        client,
        data={
            "output_refs": [
                {
                    "url": "http://169.254.169.254/latest/meta-data",
                    "name": "meta.txt",
                    "required": True,
                }
            ]
        },
        headers={"Authorization": "Bearer lease-token"},
        org_id="org-1",
        run_id="run-1",
        attempt_id="att-1",
        gateway_url="http://hermes:8642",
    )
    assert failed is True
    assert events == []
    store.assert_not_called()
    client.get.assert_not_called()


@pytest.mark.asyncio
async def test_aggregate_run_terminal_missing_required_is_artifact_persist_failed():
    db = AsyncMock()
    dummy_running = MagicMock(status="WAITING_EDGE", run_id="r2", org_id="org-1")
    dummy_failed = MagicMock(status="FAILED", run_id="r2", org_id="org-1")
    steps = [
        {
            "step_id": "s1",
            "required": True,
            "status": "SUCCEEDED",
            "required_artifacts": ["output.csv"],
            "result": {"data": "done"},
        }
    ]
    mock_steps = MagicMock()
    mock_steps.mappings.return_value.all.return_value = steps
    with patch("app.services.run_service.get_run", side_effect=[dummy_running, dummy_failed]), patch(
        "app.services.run_service.list_artifacts",
        return_value=[],
    ), patch("app.services.run_service.set_status", return_value=True) as mock_set, patch(
        "app.services.run_service.append_event",
        return_value=MagicMock(),
    ):
        db.execute = AsyncMock(return_value=mock_steps)
        res = await run_service.aggregate_run_terminal(db, "r2", org_id="org-1")
        assert res.status == "FAILED"
        assert mock_set.call_args[0][2] == "FAILED"
        assert mock_set.call_args.kwargs["result"]["error_code"] == ARTIFACT_PERSIST_FAILED

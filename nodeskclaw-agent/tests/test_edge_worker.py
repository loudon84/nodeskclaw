from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.edge_worker import EdgeWorker


@pytest.mark.asyncio
async def test_edge_worker_heartbeat_then_jobs_poll(monkeypatch):
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_CENTRAL_BASE_URL", "http://central.test")
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_EDGE_TOKEN", "edge-token")
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_EDGE_NODE_ID", "node-1")
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_EDGE_POLL_SECONDS", 0.01)

    heartbeat_response = MagicMock()
    heartbeat_response.raise_for_status = MagicMock()
    jobs_response = MagicMock()
    jobs_response.status_code = 204
    jobs_response.raise_for_status = MagicMock()
    jobs_response.content = b""

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.post = AsyncMock(return_value=heartbeat_response)
    client.get = AsyncMock(return_value=jobs_response)

    worker = EdgeWorker()

    async def stop_soon():
        await worker._heartbeat(client)
        job = await worker._claim_job(client)
        assert job is None
        worker.stop()

    with patch("app.services.edge_worker.httpx.AsyncClient", return_value=client):
        await stop_soon()

    client.post.assert_awaited()
    heartbeat_call = client.post.await_args
    assert heartbeat_call.args[0] == "http://central.test/api/v1/internal/edge/heartbeat"
    assert heartbeat_call.kwargs["headers"]["X-Edge-Token"] == "edge-token"
    assert heartbeat_call.kwargs["json"]["node_id"] == "node-1"

    client.get.assert_awaited()
    jobs_call = client.get.await_args
    assert jobs_call.args[0] == "http://central.test/api/v1/internal/edge/jobs"
    assert jobs_call.kwargs["headers"]["X-Edge-Token"] == "edge-token"


@pytest.mark.asyncio
async def test_edge_worker_incremental_events_and_spool(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_CENTRAL_BASE_URL", "http://central.test")
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_EDGE_TOKEN", "edge-token")
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_EDGE_NODE_ID", "node-1")

    worker = EdgeWorker()
    worker._spool_dir = tmp_path

    # Simulate connector streaming events
    async def mock_execute(*args, **kwargs):
        yield {"event_type": "custom.step", "payload": {"n": 1}}
        yield {"event_type": "run.completed", "payload": {"result": "ok"}}

    monkeypatch.setattr("app.services.edge_worker.execute_connector_run", mock_execute)

    # 1. Post succeeds
    client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    client.post = AsyncMock(return_value=mock_resp)

    job = {"id": "job-100", "tool_name": "test", "arguments": {}, "snapshot": {}, "delivery_generation": 3}
    await worker._execute_job(client, job)

    assert client.post.call_count == 2
    first_call_body = client.post.call_args_list[0].kwargs["json"]["events"][0]
    assert first_call_body["event_type"] == "custom.step"
    assert first_call_body["source"] == "edge"
    assert "job-100" in first_call_body["source_event_id"]
    assert first_call_body["delivery_generation"] == 3
    assert client.post.call_args_list[0].kwargs["headers"]["X-Delivery-Generation"] == "3"
    assert client.post.call_args_list[0].kwargs["json"]["delivery_generation"] == 3

    # 2. Post fails -> spool to disk
    client_fail = AsyncMock()
    client_fail.post = AsyncMock(side_effect=Exception("network error"))
    await worker._execute_job(client_fail, job)

    spool_files = list(tmp_path.glob("*.json"))
    assert len(spool_files) == 2

    # 3. Flush spool
    client_recover = AsyncMock()
    client_recover.post = AsyncMock(return_value=mock_resp)
    await worker._flush_spool(client_recover)
    assert len(list(tmp_path.glob("*.json"))) == 0


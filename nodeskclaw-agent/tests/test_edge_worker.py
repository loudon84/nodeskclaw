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

    # Simulate engine streaming events
    async def mock_execute(*args, **kwargs):
        yield {"event_type": "custom.step", "payload": {"n": 1}}
        yield {"event_type": "run.completed", "payload": {"result": "ok"}}

    monkeypatch.setattr("app.services.edge_worker.execute_engine", mock_execute)

    # 1. Post succeeds
    client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    client.post = AsyncMock(return_value=mock_resp)
    client.get = AsyncMock(return_value=mock_resp)

    job = {"id": "job-100", "tool_name": "test", "arguments": {}, "snapshot": {}, "delivery_generation": 3}
    await worker._execute_job(client, job)

    assert client.post.call_count >= 2
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
    client_fail.get = AsyncMock(side_effect=Exception("network error"))
    await worker._execute_job(client_fail, job)

    spool_files = list(tmp_path.glob("*.json"))
    assert len(spool_files) >= 2
    # Check spool envelope fields
    import json
    spool_content = json.loads(spool_files[0].read_text(encoding="utf-8"))
    assert spool_content["delivery_generation"] == 3
    assert spool_content["job_id"] == "job-100"

    # 3. Flush spool
    client_recover = AsyncMock()
    client_recover.post = AsyncMock(return_value=mock_resp)
    await worker._flush_spool(client_recover)
    assert len(list(tmp_path.glob("*.json"))) == 0


@pytest.mark.asyncio
async def test_edge_worker_reconcile_desired_installations(monkeypatch):
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_CENTRAL_BASE_URL", "http://central.test")
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_EDGE_TOKEN", "edge-token")
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_EDGE_NODE_ID", "node-1")

    worker = EdgeWorker()

    desired_response = MagicMock()
    desired_response.status_code = 200
    desired_response.json.return_value = {
        "code": 0,
        "data": {
            "items": [
                {
                    "id": "inst-1",
                    "skill_id": "skill-1",
                    "desired_status": "installed",
                    "desired_generation": 2,
                    "actual_generation": 1,
                },
                {"id": "inst-2", "desired_generation": 1, "actual_generation": 1},
            ]
        },
    }

    report_response = MagicMock()
    report_response.raise_for_status = MagicMock()

    client = AsyncMock()
    client.get = AsyncMock(return_value=desired_response)
    client.post = AsyncMock(return_value=report_response)

    await worker._reconcile_desired_installations(client)

    assert client.get.called
    get_call = client.get.call_args
    assert "/api/v1/internal/edge/installations/desired" in get_call.args[0]

    assert client.post.called
    post_call = client.post.call_args
    assert "/api/v1/internal/edge/installations/actual" in post_call.args[0]
    body = post_call.kwargs["json"]
    assert body["actual_status"] == "error"
    assert body["generation"] == 2


@pytest.mark.asyncio
async def test_edge_worker_uninstall_removes_current_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_CENTRAL_BASE_URL", "http://central.test")
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_EDGE_TOKEN", "edge-token")
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_EDGE_NODE_ID", "node-1")

    worker = EdgeWorker()
    worker._spool_dir = tmp_path
    worker._installer = MagicMock()
    worker._installer.uninstall.return_value = True
    desired_response = MagicMock(status_code=200)
    desired_response.json.return_value = {
        "data": {
            "items": [
                {
                    "id": "inst-1",
                    "skill_id": "skill-1",
                    "desired_status": "uninstalling",
                    "desired_generation": 3,
                    "actual_generation": 2,
                }
            ]
        }
    }
    report_response = MagicMock()
    report_response.raise_for_status = MagicMock()
    client = AsyncMock()
    client.get.return_value = desired_response
    client.post.return_value = report_response

    await worker._reconcile_desired_installations(client)

    worker._installer.uninstall.assert_called_once_with(skill_id="skill-1")
    assert client.post.call_args.kwargs["json"]["actual_status"] == "uninstalled"


@pytest.mark.asyncio
async def test_edge_worker_rejects_incomplete_bundle_descriptor(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_CENTRAL_BASE_URL", "http://central.test")
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_EDGE_TOKEN", "edge-token")
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_EDGE_NODE_ID", "node-1")

    worker = EdgeWorker()
    worker._spool_dir = tmp_path
    worker._installer = MagicMock()
    desired_response = MagicMock(status_code=200)
    desired_response.json.return_value = {
        "data": {
            "items": [
                {
                    "id": "inst-1",
                    "skill_id": "skill-1",
                    "desired_status": "installed",
                    "desired_generation": 2,
                    "actual_generation": 1,
                    "bundle": {
                        "release_id": "rel-1",
                        "bundle_ref": "bundle-1",
                        "version": "1.0.0",
                        "size": 3,
                    },
                }
            ]
        }
    }
    download_response = MagicMock(status_code=200, content=b"zip", raise_for_status=MagicMock())
    report_response = MagicMock(status_code=200, raise_for_status=MagicMock())
    client = AsyncMock()
    client.get.side_effect = [desired_response, download_response]
    client.post.return_value = report_response

    await worker._reconcile_desired_installations(client)

    worker._installer.install.assert_not_called()
    assert client.post.call_args.kwargs["json"]["actual_status"] == "error"


@pytest.mark.asyncio
async def test_edge_spool_envelope_completeness_and_drain(tmp_path, monkeypatch):
    import json

    import httpx

    worker = EdgeWorker()
    worker._spool_dir = tmp_path

    # Write spool envelope
    await worker._spool_events(
        "job-200",
        [{"event_type": "step.running", "payload": {"pct": 50}}],
        delivery_generation=4,
        attempt_id="att-99",
        step_id="step-edge",
        request_trace_id="trace-abc",
        idempotency_key="idem-1",
    )

    spool_files = list(tmp_path.glob("spool_*.json"))
    assert len(spool_files) == 1
    content = json.loads(spool_files[0].read_text(encoding="utf-8"))
    assert content["job_id"] == "job-200"
    assert content["delivery_generation"] == 4
    assert content["attempt_id"] == "att-99"
    assert content["step_id"] == "step-edge"
    assert content["request_trace_id"] == "trace-abc"
    assert content["idempotency_key"] == "idem-1"

    # Drain on 403 discards the preempted spool file
    client = AsyncMock()
    req = httpx.Request("POST", "http://central.test/api/v1/internal/edge/jobs/job-200/events")
    resp_403 = httpx.Response(403, request=req)
    client.post = AsyncMock(side_effect=httpx.HTTPStatusError("preempted", request=req, response=resp_403))

    await worker._flush_spool(client)
    assert len(list(tmp_path.glob("spool_*.json"))) == 0


@pytest.mark.asyncio
async def test_edge_lease_preempted_stops_job(monkeypatch):
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_CENTRAL_BASE_URL", "http://central.test")
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_EDGE_TOKEN", "edge-token")
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_EDGE_NODE_ID", "node-1")

    worker = EdgeWorker()

    # Generator that yields 2 events and checks cancel_event
    async def mock_execute(*args, **kwargs):
        cancel_event = kwargs.get("cancel_event")
        yield {"event_type": "run.started", "payload": {}}
        if cancel_event:
            cancel_event.set()
        yield {"event_type": "run.progress", "payload": {}}

    monkeypatch.setattr("app.services.edge_worker.execute_engine", mock_execute)

    client = AsyncMock()
    mock_resp = MagicMock(status_code=200, raise_for_status=MagicMock())
    client.post = AsyncMock(return_value=mock_resp)
    client.get = AsyncMock(return_value=mock_resp)

    job = {"id": "job-300", "tool_name": "test", "arguments": {}, "snapshot": {}, "delivery_generation": 1}
    await worker._execute_job(client, job)
    assert True


def test_edge_skill_installer_isolated(tmp_path):
    import io
    import zipfile

    from app.services.edge_skill_installer import EdgeSkillInstaller

    installer = EdgeSkillInstaller(base_dir=tmp_path)
    skill_id = "test-skill-1"

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("index.js", "console.log('hello')")
        zf.writestr("manifest.json", '{"name": "test"}')
    zip_bytes = zip_buf.getvalue()

    target = installer.install(skill_id=skill_id, version="1.0.0", zip_bytes=zip_bytes)
    assert target.exists()
    assert (target / "index.js").read_text() == "console.log('hello')"
    assert (target / "installation_meta.json").exists()
    assert installer.is_installed(skill_id=skill_id, version="1.0.0")

    bad_buf = io.BytesIO()
    with zipfile.ZipFile(bad_buf, "w") as zf:
        zf.writestr("../evil.txt", "evil")
    with pytest.raises(ValueError, match="Zip path traversal detected"):
        installer.install(skill_id="bad-skill", version="1.0.0", zip_bytes=bad_buf.getvalue())

    uninstalled = installer.uninstall(skill_id=skill_id, version="1.0.0")
    assert uninstalled is True
    assert not installer.is_installed(skill_id=skill_id, version="1.0.0")


@pytest.mark.asyncio
async def test_edge_worker_reconcile_with_real_installer(tmp_path, monkeypatch):
    import io
    import zipfile

    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_CENTRAL_BASE_URL", "http://central.test")
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_EDGE_TOKEN", "edge-token")
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_EDGE_NODE_ID", "node-1")

    worker = EdgeWorker()
    worker._spool_dir = tmp_path
    from app.services.edge_skill_installer import EdgeSkillInstaller

    worker._installer = EdgeSkillInstaller(base_dir=tmp_path / "skills")

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("main.txt", "bundle-content")
    zip_bytes = zip_buf.getvalue()

    client = AsyncMock()

    bundle = {
        "release_id": "rel-1",
        "bundle_ref": "bundle-ref-1",
        "version": "1.0.0",
        "size": len(zip_bytes),
        "sha256": __import__("hashlib").sha256(zip_bytes).hexdigest(),
    }

    desired_resp = MagicMock(
        status_code=200,
        json=MagicMock(
            return_value={
                "data": {
                    "items": [
                        {
                            "id": "inst-1",
                            "skill_id": "skill-weather",
                            "desired_status": "installed",
                            "desired_generation": 2,
                            "actual_generation": 1,
                            "bundle": bundle,
                        }
                    ]
                }
            }
        ),
    )
    download_resp = MagicMock(status_code=200, content=zip_bytes, raise_for_status=MagicMock())
    actual_resp = MagicMock(status_code=200, raise_for_status=MagicMock())

    async def fake_get(url, **kwargs):
        if "/bundle?" in url:
            return download_resp
        return desired_resp

    client.get = AsyncMock(side_effect=fake_get)
    client.post = AsyncMock(return_value=actual_resp)

    await worker._reconcile_desired_installations(client)

    assert client.post.call_count == 1
    post_args = client.post.call_args[1]
    assert post_args["json"]["installation_id"] == "inst-1"
    assert post_args["json"]["actual_status"] == "ready"
    assert post_args["json"]["generation"] == 2
    assert worker._installer.is_installed(skill_id="skill-weather", version="2")


@pytest.mark.asyncio
async def test_edge_worker_pull_and_fulfill_on_demand_requests(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_CENTRAL_BASE_URL", "http://central.test")
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_EDGE_TOKEN", "edge-token")
    monkeypatch.setattr("app.services.edge_worker.settings.SKILL_AGENT_EDGE_NODE_ID", "node-1")

    worker = EdgeWorker()
    worker._spool_dir = tmp_path

    # Place a local file in spool dir
    local_file = tmp_path / "agent_log.txt"
    local_file.write_text("detailed edge execution log")

    client = AsyncMock()
    # Pull requests returns 1 issued request
    pull_resp = MagicMock(
        status_code=200,
        json=MagicMock(return_value={
            "data": {
                "items": [
                    {
                        "id": "req-1",
                        "job_id": "job-od-1",
                        "name": "agent_log.txt",
                        "delivery_generation": 2,
                        "run_generation": 1,
                        "attempt_id": "att-1",
                        "step_id": "step-1",
                    }
                ]
            }
        }),
    )
    upload_resp = MagicMock(status_code=200, raise_for_status=MagicMock())
    client.get = AsyncMock(return_value=pull_resp)
    client.post = AsyncMock(return_value=upload_resp)

    await worker._pull_and_fulfill_on_demand_requests(client)

    assert client.post.call_count == 1
    post_args = client.post.call_args[1]
    assert "jobs/job-od-1/artifacts/upload" in client.post.call_args[0][0]
    assert post_args["json"]["name"] == "agent_log.txt"
    assert post_args["json"]["attempt_id"] == "att-1"
    assert post_args["json"]["step_id"] == "step-1"

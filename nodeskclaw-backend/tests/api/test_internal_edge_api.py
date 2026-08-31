"""Unit tests for Backend Internal Edge Delivery Envelope and generation fencing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.internal_edge import EdgeJobEventsBody, post_edge_job_events
from app.core.exceptions import ForbiddenError
from app.models.connector.edge_job import EdgeJob, EdgeJobStatus
from app.models.connector.edge_node import EdgeNode, EdgeNodeStatus


@pytest.mark.asyncio
async def test_post_edge_job_events_rejects_missing_generation():
    db = AsyncMock()
    node = EdgeNode()
    node.id = "node-1"
    node.org_id = "org-1"
    node.status = EdgeNodeStatus.ONLINE.value

    job = EdgeJob()
    job.id = "job-1"
    job.edge_node_id = "node-1"
    job.org_id = "org-1"
    job.delivery_generation = 2
    job.status = EdgeJobStatus.CLAIMED.value

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = job
    db.execute = AsyncMock(return_value=mock_res)

    body = EdgeJobEventsBody(events=[{"event_type": "run.progress", "payload": {}}], delivery_generation=None)

    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        with pytest.raises(ForbiddenError, match="delivery generation"):
            await post_edge_job_events("job-1", body, db, x_edge_token="tok", x_delivery_generation=None)


@pytest.mark.asyncio
async def test_post_edge_job_events_rejects_stale_generation():
    db = AsyncMock()
    node = EdgeNode()
    node.id = "node-1"
    node.org_id = "org-1"
    node.status = EdgeNodeStatus.ONLINE.value

    job = EdgeJob()
    job.id = "job-1"
    job.edge_node_id = "node-1"
    job.org_id = "org-1"
    job.delivery_generation = 3
    job.status = EdgeJobStatus.CLAIMED.value

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = job
    db.execute = AsyncMock(return_value=mock_res)

    body = EdgeJobEventsBody(events=[{"event_type": "run.progress", "payload": {}}], delivery_generation=2)

    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        with pytest.raises(ForbiddenError, match="stale_delivery_generation"):
            await post_edge_job_events("job-1", body, db, x_edge_token="tok", x_delivery_generation="2")


@pytest.mark.asyncio
async def test_renew_edge_job_lease_success_and_fencing():
    from app.api.internal_edge import EdgeLeaseRenewBody, renew_edge_job_lease

    db = AsyncMock()
    node = EdgeNode()
    node.id = "node-1"
    node.org_id = "org-1"
    node.status = EdgeNodeStatus.ONLINE.value

    job = EdgeJob()
    job.id = "job-1"
    job.edge_node_id = "node-1"
    job.org_id = "org-1"
    job.delivery_generation = 2
    job.status = EdgeJobStatus.CLAIMED.value

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = job
    db.execute = AsyncMock(return_value=mock_res)

    # 1. Matching generation succeeds
    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        res = await renew_edge_job_lease("job-1", EdgeLeaseRenewBody(delivery_generation=2), db, x_edge_token="tok")
    assert res["code"] == 0
    assert res["data"]["delivery_generation"] == 2
    assert res["data"]["lease_until"] is not None

    # 2. Stale generation rejected
    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        with pytest.raises(ForbiddenError, match="stale_delivery_generation"):
            await renew_edge_job_lease("job-1", EdgeLeaseRenewBody(delivery_generation=1), db, x_edge_token="tok")


@pytest.mark.asyncio
async def test_edge_job_cancel_check_and_request():
    from app.api.internal_edge import check_edge_job_cancel, request_edge_job_cancel

    db = AsyncMock()
    node = EdgeNode()
    node.id = "node-1"
    node.org_id = "org-1"
    node.status = EdgeNodeStatus.ONLINE.value

    job = EdgeJob()
    job.id = "job-1"
    job.edge_node_id = "node-1"
    job.org_id = "org-1"
    job.status = EdgeJobStatus.RUNNING.value
    job.cancel_requested_at = None

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = job
    db.execute = AsyncMock(return_value=mock_res)

    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        # Initially not cancelled
        res1 = await check_edge_job_cancel("job-1", db, x_edge_token="tok")
        assert res1["data"]["cancel_requested"] is False

        # Request cancel
        res2 = await request_edge_job_cancel("job-1", db, x_edge_token="tok")
        assert res2["data"]["cancel_requested"] is True
        assert job.cancel_requested_at is not None

        # Check again
        res3 = await check_edge_job_cancel("job-1", db, x_edge_token="tok")
        assert res3["data"]["cancel_requested"] is True


@pytest.mark.asyncio
async def test_upload_edge_job_artifact():
    import base64
    import hashlib
    from app.api.internal_edge import EdgeArtifactUploadBody, upload_edge_job_artifact
    from app.core.exceptions import BadRequestError

    db = AsyncMock()
    node = EdgeNode()
    node.id = "node-1"
    node.org_id = "org-1"
    node.status = EdgeNodeStatus.ONLINE.value

    job = EdgeJob()
    job.id = "job-1"
    job.run_id = "run-1"
    job.edge_node_id = "node-1"
    job.org_id = "org-1"
    job.delivery_generation = 2
    job.status = EdgeJobStatus.RUNNING.value

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = job
    db.execute = AsyncMock(return_value=mock_res)

    content = b'{"output": 42}'
    content_b64 = base64.b64encode(content).decode()
    sha = hashlib.sha256(content).hexdigest()

    # 1. Valid upload
    body = EdgeArtifactUploadBody(
        artifact_id="art-1",
        name="result.json",
        content_type="application/json",
        content_base64=content_b64,
        checksum_sha256=sha,
        delivery_generation=2,
    )
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.post = AsyncMock(return_value=mock_resp)

    with (
        patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)),
        patch("app.api.internal_edge.httpx.AsyncClient", return_value=mock_client),
    ):
        res = await upload_edge_job_artifact("job-1", body, db, x_edge_token="tok")
    assert res["code"] == 0
    assert res["data"]["artifact_id"] == "art-1"
    assert res["data"]["checksum_sha256"] == sha

    # 2. Checksum mismatch fails
    bad_body = EdgeArtifactUploadBody(
        artifact_id="art-1",
        name="result.json",
        content_type="application/json",
        content_base64=content_b64,
        checksum_sha256="wrong-sha256",
        delivery_generation=2,
    )
    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        with pytest.raises(BadRequestError, match="checksum_mismatch"):
            await upload_edge_job_artifact("job-1", bad_body, db, x_edge_token="tok")


@pytest.mark.asyncio
async def test_get_desired_installations():
    from app.api.internal_edge import get_desired_installations
    from app.models.hermes_skill.skill_installation import HermesSkillInstallation

    db = AsyncMock()
    node = EdgeNode()
    node.id = "node-1"
    node.org_id = "org-1"
    node.status = EdgeNodeStatus.ONLINE.value

    inst = HermesSkillInstallation()
    inst.id = "inst-1"
    inst.org_id = "org-1"
    inst.skill_id = "calculator"
    inst.target_kind = "edge"
    inst.edge_node_id = "node-1"
    inst.status = "installed"
    inst.desired_generation = 2
    inst.actual_generation = 1
    inst.install_metadata = {"pkg": "calc"}
    inst.routing_metadata = {}

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [inst]
    db.execute = AsyncMock(return_value=mock_res)

    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        res = await get_desired_installations(db, x_edge_token="tok")
    assert res["code"] == 0
    assert len(res["data"]["items"]) == 1
    item = res["data"]["items"][0]
    assert item["id"] == "inst-1"
    assert item["skill_id"] == "calculator"
    assert item["desired_generation"] == 2
    assert item["actual_generation"] == 1


@pytest.mark.asyncio
async def test_get_desired_installations_pins_bundle(tmp_path, monkeypatch):
    from app.api.internal_edge import get_desired_installations
    from app.models.hermes_skill.skill_installation import HermesSkillInstallation
    from app.models.hermes_skill.skill_release import HermesSkillRelease

    db = AsyncMock()
    node = EdgeNode()
    node.id = "node-1"
    node.org_id = "org-1"
    node.status = EdgeNodeStatus.ONLINE.value

    inst = HermesSkillInstallation()
    inst.id = "inst-1"
    inst.org_id = "org-1"
    inst.skill_id = "calculator"
    inst.target_kind = "edge"
    inst.edge_node_id = "node-1"
    inst.status = "installed"
    inst.desired_generation = 2
    inst.actual_generation = 1
    inst.install_metadata = {"pkg": "calc"}
    inst.routing_metadata = {}

    release = HermesSkillRelease()
    release.id = "rel-1"
    release.bundle_ref = "11111111-1111-4111-8111-111111111111"
    release.bundle_sha256 = "abc123"
    release.bundle_size_bytes = 42
    release.version = "1.0.0"

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [inst]
    db.execute = AsyncMock(return_value=mock_res)
    db.commit = AsyncMock()
    db.flush = AsyncMock()

    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)), patch(
        "app.api.internal_edge.SkillReleaseService.get_published", AsyncMock(return_value=release)
    ):
        res = await get_desired_installations(db, x_edge_token="tok")

    item = res["data"]["items"][0]
    assert item["bundle"]["release_id"] == "rel-1"
    assert item["bundle"]["bundle_ref"] == "11111111-1111-4111-8111-111111111111"
    assert item["bundle"]["sha256"] == "abc123"
    assert item["bundle"]["size"] == 42
    assert "releases/" not in str(item)
    assert inst.install_metadata["published_bundle"]["generation"] == 2


@pytest.mark.asyncio
async def test_download_installation_bundle_generation_fencing(tmp_path, monkeypatch):
    from app.api.internal_edge import download_installation_bundle
    from app.models.hermes_skill.skill_installation import HermesSkillInstallation

    db = AsyncMock()
    node = EdgeNode()
    node.id = "node-1"
    node.org_id = "org-1"
    node.status = EdgeNodeStatus.ONLINE.value

    inst = HermesSkillInstallation()
    inst.id = "inst-1"
    inst.org_id = "org-1"
    inst.skill_id = "calculator"
    inst.target_kind = "edge"
    inst.edge_node_id = "node-1"
    inst.status = "installed"
    inst.desired_generation = 2
    inst.install_metadata = {
        "published_bundle": {
            "generation": 2,
            "release_id": "rel-1",
            "bundle_ref": "11111111-1111-4111-8111-111111111111",
            "version": "1.0.0",
            "size": 5,
            "sha256": "deadbeef",
        }
    }

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = inst
    db.execute = AsyncMock(return_value=mock_res)
    db.commit = AsyncMock()

    hub_root = tmp_path / "hub"
    releases_dir = hub_root / "releases"
    releases_dir.mkdir(parents=True)
    zip_bytes = b"hello"
    (releases_dir / "11111111-1111-4111-8111-111111111111.zip").write_bytes(zip_bytes)
    monkeypatch.setattr(
        "app.api.internal_edge.settings.HERMES_SKILL_HUB_ROOT",
        str(hub_root),
    )

    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        response = await download_installation_bundle("inst-1", generation=2, db=db, x_edge_token="tok")
    chunks: list[bytes] = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)
    assert b"".join(chunks) == zip_bytes

    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        with pytest.raises(ForbiddenError, match="stale_actual_generation"):
            await download_installation_bundle("inst-1", generation=1, db=db, x_edge_token="tok")


@pytest.mark.asyncio
async def test_download_installation_bundle_requires_exact_node_binding():
    from app.api.internal_edge import download_installation_bundle
    from app.models.hermes_skill.skill_installation import HermesSkillInstallation

    db = AsyncMock()
    node = EdgeNode()
    node.id = "node-1"
    node.org_id = "org-1"
    node.status = EdgeNodeStatus.ONLINE.value

    inst = HermesSkillInstallation()
    inst.id = "inst-1"
    inst.org_id = "org-1"
    inst.target_kind = "edge"
    inst.edge_node_id = None
    inst.status = "installed"
    inst.desired_generation = 2

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = inst
    db.execute = AsyncMock(return_value=mock_res)

    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        with pytest.raises(ForbiddenError, match="org/node"):
            await download_installation_bundle("inst-1", generation=2, db=db, x_edge_token="tok")


@pytest.mark.asyncio
async def test_claim_expired_lease_reclaim_with_generation_bump():
    from datetime import datetime, timezone, timedelta
    from app.api.internal_edge import claim_edge_job

    db = AsyncMock()
    node = EdgeNode()
    node.id = "node-1"
    node.org_id = "org-1"
    node.status = EdgeNodeStatus.ONLINE.value

    # Job currently claimed with expired lease
    job = EdgeJob()
    job.id = "job-expired"
    job.run_id = "run-1"
    job.edge_node_id = "node-1"
    job.org_id = "org-1"
    job.status = EdgeJobStatus.CLAIMED.value
    job.delivery_generation = 1
    job.lease_until = datetime.now(timezone.utc) - timedelta(seconds=10)
    job.arguments = {}
    job.snapshot = {}
    job.tool_name = "test_tool"
    job.attempt_id = "att-1"
    job.step_id = "step-1"
    job.run_generation = 1
    job.request_trace_id = "trace-1"

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = job
    db.execute = AsyncMock(return_value=mock_res)

    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        claimed_job = await claim_edge_job(db, x_edge_token="tok")

    assert claimed_job["id"] == "job-expired"
    assert claimed_job["delivery_generation"] == 2
    assert job.delivery_generation == 2
    assert job.lease_until is not None


@pytest.mark.asyncio
async def test_post_edge_job_events_rejects_payload_too_large():
    from app.core.exceptions import BadRequestError

    db = AsyncMock()
    node = EdgeNode()
    node.id = "node-1"
    node.org_id = "org-1"
    node.status = EdgeNodeStatus.ONLINE.value

    job = EdgeJob()
    job.id = "job-large"
    job.edge_node_id = "node-1"
    job.org_id = "org-1"
    job.delivery_generation = 1
    job.status = EdgeJobStatus.RUNNING.value

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = job
    db.execute = AsyncMock(return_value=mock_res)

    huge_payload = {"large_data": "x" * 70000}
    body = EdgeJobEventsBody(
        events=[{"event_type": "run.completed", "payload": huge_payload}],
        delivery_generation=1,
    )

    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        with pytest.raises(BadRequestError, match="payload_too_large"):
            await post_edge_job_events("job-large", body, db, x_edge_token="tok", x_delivery_generation="1")


@pytest.mark.asyncio
async def test_upload_edge_job_artifact_relays_and_transmits_error():
    import base64
    import hashlib
    import httpx
    from app.api.internal_edge import EdgeArtifactUploadBody, upload_edge_job_artifact
    from app.core.exceptions import ConflictError

    db = AsyncMock()
    node = EdgeNode()
    node.id = "node-1"
    node.org_id = "org-1"
    node.status = EdgeNodeStatus.ONLINE.value

    job = EdgeJob()
    job.id = "job-art-1"
    job.run_id = "run-1"
    job.edge_node_id = "node-1"
    job.org_id = "org-1"
    job.delivery_generation = 1
    job.run_generation = 2
    job.attempt_id = "att-1"
    job.step_id = "step-1"

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = job
    db.execute = AsyncMock(return_value=mock_res)

    content = b"hello artifact bytes"
    b64_content = base64.b64encode(content).decode()
    chk = hashlib.sha256(content).hexdigest()

    body = EdgeArtifactUploadBody(
        name="output.txt",
        content_base64=b64_content,
        checksum_sha256=chk,
        delivery_generation=1,
        idempotency_key="idem-key-1",
    )

    # 1. Success relay
    mock_response = MagicMock()
    mock_response.is_error = False
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "artifact_id": "art-101",
        "name": "output.txt",
        "storage_state": "persisted",
        "checksum_sha256": chk,
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)), \
         patch("httpx.AsyncClient", return_value=mock_client), \
         patch("app.api.internal_edge.settings.SKILL_AGENT_ENABLED", True), \
         patch("app.api.internal_edge.settings.SKILL_AGENT_BASE_URL", "http://agent:4580"):
        res = await upload_edge_job_artifact("job-art-1", body, db, x_edge_token="tok", x_delivery_generation="1")

    assert res["code"] == 0
    assert res["data"]["artifact_id"] == "art-101"
    # Verify destination URL matches /internal/v1/runs/{run_id}/artifacts
    called_url = mock_client.post.call_args[0][0]
    assert called_url == "http://agent:4580/internal/v1/runs/run-1/artifacts"
    called_json = mock_client.post.call_args[1]["json"]
    assert called_json["idempotency_key"] == "idem-key-1"
    assert called_json["generation"] == 2

    # 2. Transmit error from Agent without rewriting to 403 ForbiddenError
    mock_err_response = MagicMock()
    mock_err_response.is_error = True
    mock_err_response.status_code = 409
    mock_err_response.json.return_value = {
        "error_code": "errors.artifact.idempotency_conflict",
        "message_key": "errors.artifact.idempotency_conflict",
        "message": "artifact idempotency conflict",
        "detail": "artifact idempotency conflict",
    }
    mock_client.post.return_value = mock_err_response

    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)), \
         patch("httpx.AsyncClient", return_value=mock_client), \
         patch("app.api.internal_edge.settings.SKILL_AGENT_ENABLED", True), \
         patch("app.api.internal_edge.settings.SKILL_AGENT_BASE_URL", "http://agent:4580"):
        with pytest.raises(ConflictError) as exc_info:
            await upload_edge_job_artifact("job-art-1", body, db, x_edge_token="tok", x_delivery_generation="1")
        assert exc_info.value.message_key == "errors.artifact.idempotency_conflict"


@pytest.mark.asyncio
async def test_edge_artifact_on_demand_requests_lifecycle():
    from app.api.internal_edge import (
        IssueOnDemandRequestBody,
        create_edge_job_artifact_on_demand_request,
        pull_edge_artifact_on_demand_requests,
    )
    from app.services.connector.edge_node_service import EdgeNodeService
    from app.models.connector.edge_artifact_on_demand_request import EdgeArtifactOnDemandRequest, OnDemandRequestStatus

    db = AsyncMock()
    node = EdgeNode()
    node.id = "node-1"
    node.org_id = "org-1"
    node.status = EdgeNodeStatus.ONLINE.value

    job = EdgeJob()
    job.id = "job-od-1"
    job.run_id = "run-1"
    job.edge_node_id = "node-1"
    job.org_id = "org-1"
    job.run_generation = 1
    job.delivery_generation = 1
    job.attempt_id = "att-1"
    job.step_id = "step-1"

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = job
    mock_res.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_res)

    # 1. Issue on-demand request
    issue_body = IssueOnDemandRequestBody(name="custom.log", ttl_seconds=600)
    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        res_issue = await create_edge_job_artifact_on_demand_request("job-od-1", issue_body, db, x_edge_token="tok")

    assert res_issue["code"] == 0
    assert res_issue["data"]["name"] == "custom.log"
    assert res_issue["data"]["status"] == "issued"

    # 2. Pull on-demand requests
    from datetime import datetime, timedelta, timezone
    mock_od_req = EdgeArtifactOnDemandRequest(
        id="od-req-1",
        org_id="org-1",
        edge_node_id="node-1",
        job_id="job-od-1",
        run_id="run-1",
        name="custom.log",
        status=OnDemandRequestStatus.ISSUED.value,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    mock_pull_res = MagicMock()
    mock_pull_res.scalars.return_value.all.return_value = [mock_od_req]
    db.execute = AsyncMock(return_value=mock_pull_res)

    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        res_pull = await pull_edge_artifact_on_demand_requests(db, x_edge_token="tok")

    assert res_pull["code"] == 0
    items = res_pull["data"]["items"]
    assert len(items) == 1
    assert items[0]["name"] == "custom.log"
    assert items[0]["status"] == "issued"

    # 3. Consume on-demand request
    mock_od_res = MagicMock()
    mock_od_res.scalar_one_or_none.return_value = mock_od_req
    db.execute = AsyncMock(return_value=mock_od_res)

    service = EdgeNodeService(db)
    consumed = await service.consume_on_demand_request(org_id="org-1", job_id="job-od-1", name="custom.log", artifact_id="art-999")
    assert consumed.status == OnDemandRequestStatus.CONSUMED.value
    assert consumed.artifact_id == "art-999"
    assert consumed.consumed_at is not None

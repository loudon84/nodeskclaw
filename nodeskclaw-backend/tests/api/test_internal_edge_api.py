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

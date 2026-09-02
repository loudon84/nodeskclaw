"""Internal edge API auth and heartbeat tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.internal_edge import is_edge_node_online
from app.core.exceptions import ForbiddenError
from app.models.connector.edge_node import EdgeNode
from app.services.connector.edge_node_service import hash_edge_token


def _mock_request() -> MagicMock:
    return MagicMock()


def test_is_edge_node_online_requires_recent_heartbeat():
    now = datetime.now(timezone.utc)
    node = EdgeNode(
        id="n1",
        org_id="org",
        name="edge-1",
        status="online",
        token_hash=hash_edge_token("tok"),
        last_heartbeat_at=now - timedelta(seconds=30),
    )
    assert is_edge_node_online(node, now=now) is True
    node.last_heartbeat_at = now - timedelta(seconds=120)
    assert is_edge_node_online(node, now=now) is False


@pytest.mark.asyncio
async def test_authenticate_edge_rejects_forged_token():
    from app.api import internal_edge
    from app.core.exceptions import ForbiddenError
    from fastapi import Request

    db = AsyncMock()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/internal/edge/jobs",
        "headers": [(b"x-edge-node-id", b"n1")],
    }
    request = Request(scope)
    with patch.object(
        internal_edge.EdgeControlChannel,
        "get_node_for_proof",
        AsyncMock(side_effect=ForbiddenError("missing proof", "errors.connector.edge_request_proof_missing")),
    ):
        with pytest.raises(ForbiddenError):
            await internal_edge._authenticate_edge(db, request)


@pytest.mark.asyncio
async def test_agent_can_cancel_its_own_org_edge_job():
    from app.api.internal_edge import request_agent_edge_job_cancel
    from app.models.connector.edge_job import EdgeJob

    db = AsyncMock()
    job = EdgeJob(
        id="job-1",
        org_id="org-1",
        edge_node_id="node-1",
        run_id="run-1",
        tool_name="tool",
        status="queued",
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = job
    db.execute = AsyncMock(return_value=result)

    with patch("app.api.internal_edge.settings.SKILL_AGENT_INTERNAL_TOKEN", "agent-token"), \
         patch("app.api.internal_edge.settings.SKILL_AGENT_INTERNAL_TOKEN_PREVIOUS", None):
        response = await request_agent_edge_job_cancel(
            job_id="job-1",
            db=db,
            x_skill_agent_token="agent-token",
            x_exec_org_id="org-1",
        )

    assert response["data"]["cancel_requested"] is True
    assert job.cancel_requested_at is not None
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_post_edge_job_events_forwards_to_agent():
    from unittest.mock import patch
    from app.api.internal_edge import post_edge_job_events, EdgeJobEventsBody
    from app.models.connector.edge_job import EdgeJob, EdgeJobStatus

    db = AsyncMock()
    node = EdgeNode(id="node-1", org_id="org-1", status="online")
    job = EdgeJob(
        id="job-1",
        run_id="run-1",
        org_id="org-1",
        edge_node_id="node-1",
        tool_name="test_tool",
        status=EdgeJobStatus.CLAIMED.value,
        delivery_generation=1,
    )

    with patch("app.api.internal_edge._authenticate_edge", new=AsyncMock(return_value=node)), \
         patch("app.api.internal_edge.httpx.AsyncClient") as client_cls, \
         patch("app.api.internal_edge.PGNotifyService.notify", new=AsyncMock()):

        exec_res = MagicMock()
        exec_res.scalar_one_or_none.return_value = job
        db.execute = AsyncMock(return_value=exec_res)

        mock_post_res = MagicMock()
        mock_post_res.raise_for_status = MagicMock()
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        client.post = AsyncMock(return_value=mock_post_res)
        client_cls.return_value = client

        body = EdgeJobEventsBody(
            events=[{"event_type": "run.started", "payload": {}}],
            delivery_generation=1,
        )
        res = await post_edge_job_events(
            job_id="job-1",
            body=body,
            request=_mock_request(),
            db=db,
        )

        assert res["code"] == 0
        assert job.status == EdgeJobStatus.RUNNING.value
        client.post.assert_awaited()
        call_args = client.post.await_args
        assert "/internal/v1/runs/run-1/events/ingest" in call_args[0][0]


@pytest.mark.asyncio
async def test_post_edge_job_events_fails_closed_on_relay_error():
    from unittest.mock import patch
    from app.api.internal_edge import post_edge_job_events, EdgeJobEventsBody
    from app.models.connector.edge_job import EdgeJob, EdgeJobStatus

    db = AsyncMock()
    node = EdgeNode(id="node-1", org_id="org-1", status="online")
    job = EdgeJob(
        id="job-1",
        run_id="run-1",
        org_id="org-1",
        edge_node_id="node-1",
        tool_name="test_tool",
        status=EdgeJobStatus.CLAIMED.value,
        delivery_generation=1,
    )

    with patch("app.api.internal_edge._authenticate_edge", new=AsyncMock(return_value=node)), \
         patch("app.api.internal_edge.httpx.AsyncClient") as client_cls:

        exec_res = MagicMock()
        exec_res.scalar_one_or_none.return_value = job
        db.execute = AsyncMock(return_value=exec_res)

        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        client.post = AsyncMock(side_effect=Exception("network down"))
        client_cls.return_value = client

        body = EdgeJobEventsBody(
            events=[{"event_type": "run.started", "payload": {}}],
            delivery_generation=1,
        )
        with pytest.raises(ForbiddenError):
            await post_edge_job_events(
                job_id="job-1",
                body=body,
                request=_mock_request(),
                db=db,
            )


@pytest.mark.asyncio
async def test_post_edge_job_events_rejects_stale_delivery_generation():
    from unittest.mock import patch
    from app.api.internal_edge import post_edge_job_events, EdgeJobEventsBody
    from app.models.connector.edge_job import EdgeJob, EdgeJobStatus

    db = AsyncMock()
    node = EdgeNode(id="node-1", org_id="org-1", status="online")
    job = EdgeJob(
        id="job-1",
        run_id="run-1",
        org_id="org-1",
        edge_node_id="node-1",
        tool_name="test_tool",
        status=EdgeJobStatus.CLAIMED.value,
        delivery_generation=2,
    )

    with patch("app.api.internal_edge._authenticate_edge", new=AsyncMock(return_value=node)):
        exec_res = MagicMock()
        exec_res.scalar_one_or_none.return_value = job
        db.execute = AsyncMock(return_value=exec_res)

        body = EdgeJobEventsBody(events=[{"event_type": "run.started", "payload": {}}], delivery_generation=1)
        with pytest.raises(ForbiddenError, match="delivery generation"):
            await post_edge_job_events(
                job_id="job-1",
                body=body,
                request=_mock_request(),
                db=db,
                x_delivery_generation="1",
            )


def test_compute_reconciled_status():
    from app.api.hermes_skill.installations_router import compute_reconciled_status
    from app.models.hermes_skill.skill_installation import HermesSkillInstallation

    # Non-edge
    inst_remote = HermesSkillInstallation(target_kind="remote", status="installed")
    assert compute_reconciled_status(inst_remote) == "installed"

    # Edge - pending_sync
    inst_edge_pending = HermesSkillInstallation(target_kind="edge", status="installed", actual_status=None)
    assert compute_reconciled_status(inst_edge_pending) == "pending_sync"

    # Edge - reconciled
    inst_edge_reconciled = HermesSkillInstallation(
        target_kind="edge",
        status="installed",
        actual_status="ready",
        desired_generation=2,
        actual_generation=2,
    )
    assert compute_reconciled_status(inst_edge_reconciled) == "reconciled"

    # Edge - drifted
    inst_edge_drifted = HermesSkillInstallation(target_kind="edge", status="installed", actual_status="failed")
    assert compute_reconciled_status(inst_edge_drifted) == "drifted"



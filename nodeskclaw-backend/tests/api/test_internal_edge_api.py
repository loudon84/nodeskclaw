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

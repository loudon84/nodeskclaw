"""Unit tests for Installation Desired/Actual status reconcile."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.internal_edge import EdgeActualReportBody, report_installation_actual
from app.core.exceptions import ForbiddenError
from app.models.connector.edge_node import EdgeNode, EdgeNodeStatus
from app.models.hermes_skill.skill_installation import HermesSkillInstallation


@pytest.mark.asyncio
async def test_report_installation_actual_success():
    db = AsyncMock()
    node = EdgeNode()
    node.id = "node-1"
    node.org_id = "org-1"
    node.status = EdgeNodeStatus.ONLINE.value

    installation = HermesSkillInstallation()
    installation.id = "inst-1"
    installation.org_id = "org-1"
    installation.edge_node_id = "node-1"
    installation.status = "installed"  # desired status
    installation.actual_status = "pending"

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = installation
    db.execute = AsyncMock(return_value=mock_res)

    body = EdgeActualReportBody(
        installation_id="inst-1",
        actual_status="healthy",
        meta={"version": "1.0.0"},
    )

    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        res = await report_installation_actual(body, db, x_edge_token="tok")

    assert res["code"] == 0
    assert res["data"]["actual_status"] == "healthy"
    assert installation.actual_status == "healthy"
    assert installation.actual_reported_at is not None
    assert db.commit.called


@pytest.mark.asyncio
async def test_report_installation_actual_rejects_node_mismatch():
    db = AsyncMock()
    node = EdgeNode()
    node.id = "node-1"
    node.org_id = "org-1"
    node.status = EdgeNodeStatus.ONLINE.value

    installation = HermesSkillInstallation()
    installation.id = "inst-1"
    installation.org_id = "org-1"
    installation.edge_node_id = "node-other"  # Bound to another edge node

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = installation
    db.execute = AsyncMock(return_value=mock_res)

    body = EdgeActualReportBody(
        installation_id="inst-1",
        actual_status="healthy",
    )

    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        with pytest.raises(ForbiddenError, match="edge_org_mismatch"):
            await report_installation_actual(body, db, x_edge_token="tok")

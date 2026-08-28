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


@pytest.mark.asyncio
async def test_report_installation_actual_generation_fencing():
    db = AsyncMock()
    node = EdgeNode()
    node.id = "node-1"
    node.org_id = "org-1"
    node.status = EdgeNodeStatus.ONLINE.value

    installation = HermesSkillInstallation()
    installation.id = "inst-1"
    installation.org_id = "org-1"
    installation.edge_node_id = "node-1"
    installation.desired_generation = 3
    installation.actual_generation = 2

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = installation
    db.execute = AsyncMock(return_value=mock_res)

    # 1. Stale actual generation (1 < 2) rejected
    stale_body = EdgeActualReportBody(
        installation_id="inst-1",
        actual_status="healthy",
        generation=1,
    )
    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        with pytest.raises(ForbiddenError, match="stale_actual_generation"):
            await report_installation_actual(stale_body, db, x_edge_token="tok")

    # 2. Modern actual generation (3 >= 2) accepted
    valid_body = EdgeActualReportBody(
        installation_id="inst-1",
        actual_status="healthy",
        generation=3,
    )
    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        res = await report_installation_actual(valid_body, db, x_edge_token="tok")
    assert res["code"] == 0
    assert installation.actual_generation == 3
    assert installation.actual_status == "healthy"


def test_compute_reconciled_status_generation_matching():
    from app.api.hermes_skill.installations_router import compute_reconciled_status

    # 1. Non-edge returns desired
    non_edge = HermesSkillInstallation()
    non_edge.target_kind = "remote"
    non_edge.status = "installed"
    assert compute_reconciled_status(non_edge) == "installed"

    # 2. Edge pending sync (actual_gen = 0, no actual status)
    edge_pending = HermesSkillInstallation()
    edge_pending.target_kind = "edge"
    edge_pending.status = "installed"
    edge_pending.desired_generation = 1
    edge_pending.actual_generation = 0
    edge_pending.actual_status = None
    assert compute_reconciled_status(edge_pending) == "pending_sync"

    # 3. Edge drifted due to generation mismatch
    edge_drifted = HermesSkillInstallation()
    edge_drifted.target_kind = "edge"
    edge_drifted.status = "installed"
    edge_drifted.desired_generation = 2
    edge_drifted.actual_generation = 1
    edge_drifted.actual_status = "installed"
    assert compute_reconciled_status(edge_drifted) == "drifted"

    # 4. Edge reconciled (generation matched + status matched)
    edge_reconciled = HermesSkillInstallation()
    edge_reconciled.target_kind = "edge"
    edge_reconciled.status = "installed"
    edge_reconciled.desired_generation = 2
    edge_reconciled.actual_generation = 2
    edge_reconciled.actual_status = "installed"
    assert compute_reconciled_status(edge_reconciled) == "reconciled"

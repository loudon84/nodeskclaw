"""Unit tests for Installation Desired/Actual status reconcile."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.internal_edge import EdgeActualReportBody, report_installation_actual
from app.core.exceptions import BadRequestError, ForbiddenError
from app.models.connector.edge_node import EdgeNode, EdgeNodeStatus
from app.models.hermes_skill.skill_installation import HermesSkillInstallation


def _mock_request() -> MagicMock:
    return MagicMock()


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
    installation.target_kind = "edge"
    installation.edge_node_id = "node-1"
    installation.status = "installed"  # desired status
    installation.actual_status = "pending"

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = installation
    db.execute = AsyncMock(return_value=mock_res)

    body = EdgeActualReportBody(
        installation_id="inst-1",
        actual_status="ready",
        generation=1,
        meta={"version": "1.0.0"},
    )

    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        res = await report_installation_actual(body, _mock_request(), db)

    assert res["code"] == 0
    assert res["data"]["actual_status"] == "ready"
    assert installation.actual_status == "ready"
    assert installation.actual_generation == 1
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
        actual_status="ready",
    )

    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        with pytest.raises(ForbiddenError, match="edge_org_mismatch"):
            await report_installation_actual(body, _mock_request(), db)


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
    installation.target_kind = "edge"
    installation.edge_node_id = "node-1"
    installation.desired_generation = 3
    installation.actual_generation = 2

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = installation
    db.execute = AsyncMock(return_value=mock_res)

    # 1. Stale actual generation (1 < 3) rejected
    stale_body = EdgeActualReportBody(
        installation_id="inst-1",
        actual_status="ready",
        generation=1,
    )
    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        with pytest.raises(ForbiddenError, match="stale_actual_generation"):
            await report_installation_actual(stale_body, _mock_request(), db)

    # 2. Future actual generation (4 > 3) rejected
    from app.core.exceptions import BadRequestError
    future_body = EdgeActualReportBody(
        installation_id="inst-1",
        actual_status="ready",
        generation=4,
    )
    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        with pytest.raises(BadRequestError, match="future_generation"):
            await report_installation_actual(future_body, _mock_request(), db)

    # 3. Matching actual generation (3 == 3) accepted
    valid_body = EdgeActualReportBody(
        installation_id="inst-1",
        actual_status="ready",
        generation=3,
    )
    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        res = await report_installation_actual(valid_body, _mock_request(), db)
    assert res["code"] == 0
    assert installation.actual_generation == 3
    assert installation.actual_status == "ready"


@pytest.mark.asyncio
async def test_report_installation_actual_error_does_not_align_generation():
    db = AsyncMock()
    node = EdgeNode()
    node.id = "node-1"
    node.org_id = "org-1"
    node.status = EdgeNodeStatus.ONLINE.value

    installation = HermesSkillInstallation()
    installation.id = "inst-1"
    installation.org_id = "org-1"
    installation.target_kind = "edge"
    installation.edge_node_id = "node-1"
    installation.desired_generation = 3
    installation.actual_generation = 1

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = installation
    db.execute = AsyncMock(return_value=mock_res)

    body = EdgeActualReportBody(
        installation_id="inst-1",
        actual_status="error",
        generation=3,
        meta={"error_code": "errors.skill.install_failed"},
    )
    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        res = await report_installation_actual(body, _mock_request(), db)
    assert res["code"] == 0
    assert installation.actual_generation == 1
    assert installation.actual_status == "error"
    assert installation.error_message == "errors.skill.install_failed"


@pytest.mark.asyncio
async def test_report_installation_actual_rejects_unknown_status():
    db = AsyncMock()
    node = EdgeNode()
    node.id = "node-1"
    node.org_id = "org-1"
    node.status = EdgeNodeStatus.ONLINE.value

    installation = HermesSkillInstallation()
    installation.id = "inst-1"
    installation.org_id = "org-1"
    installation.target_kind = "edge"
    installation.edge_node_id = "node-1"
    installation.desired_generation = 3
    installation.actual_generation = 1

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = installation
    db.execute = AsyncMock(return_value=mock_res)
    body = EdgeActualReportBody(installation_id="inst-1", actual_status="unknown", generation=3)

    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        with pytest.raises(BadRequestError, match="Actual status"):
            await report_installation_actual(body, _mock_request(), db)

    assert installation.actual_generation == 1


@pytest.mark.asyncio
async def test_report_installation_actual_rejects_non_edge_target():
    db = AsyncMock()
    node = EdgeNode()
    node.id = "node-1"
    node.org_id = "org-1"
    node.status = EdgeNodeStatus.ONLINE.value

    installation = HermesSkillInstallation()
    installation.id = "inst-1"
    installation.org_id = "org-1"
    installation.target_kind = "remote"
    installation.edge_node_id = "node-1"
    installation.desired_generation = 3
    installation.actual_generation = 1

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = installation
    db.execute = AsyncMock(return_value=mock_res)
    body = EdgeActualReportBody(installation_id="inst-1", actual_status="ready", generation=3)

    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        with pytest.raises(ForbiddenError, match="Edge Installation"):
            await report_installation_actual(body, _mock_request(), db)

    assert installation.actual_generation == 1


@pytest.mark.asyncio
async def test_report_installation_actual_rejects_uninstalled_for_active_desired_state():
    db = AsyncMock()
    node = EdgeNode()
    node.id = "node-1"
    node.org_id = "org-1"
    node.status = EdgeNodeStatus.ONLINE.value

    installation = HermesSkillInstallation()
    installation.id = "inst-1"
    installation.org_id = "org-1"
    installation.target_kind = "edge"
    installation.edge_node_id = "node-1"
    installation.status = "installed"
    installation.desired_generation = 3
    installation.actual_generation = 1

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = installation
    db.execute = AsyncMock(return_value=mock_res)
    body = EdgeActualReportBody(installation_id="inst-1", actual_status="uninstalled", generation=3)

    with patch("app.api.internal_edge._authenticate_edge", AsyncMock(return_value=node)):
        with pytest.raises(BadRequestError, match="Actual status"):
            await report_installation_actual(body, _mock_request(), db)

    assert installation.actual_generation == 1


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

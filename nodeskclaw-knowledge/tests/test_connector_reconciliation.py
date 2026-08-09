"""Connector reconciliation unit tests."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import ConnectorSourceObjectState, ConnectorSyncItemStatus, ConnectorSyncRunStatus
from app.services import connector_reconciliation_service


@pytest.mark.asyncio
async def test_reconcile_source_object_missing_source_file():
    obj = SimpleNamespace(
        id="so1",
        source_file_id="missing-sf",
        state=ConnectorSourceObjectState.active.value,
        last_error=None,
        deleted_at=None,
    )

    async def _get(model, pk):
        if pk == "missing-sf":
            return None
        return None

    db = MagicMock()
    db.get = AsyncMock(side_effect=_get)

    obj_result = MagicMock()
    obj_result.scalars.return_value.all.return_value = [obj]
    empty = MagicMock()
    empty.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(side_effect=[obj_result, empty, empty, empty])

    report = await connector_reconciliation_service.reconcile_connector_links(db)
    assert report.drifted >= 1
    assert report.repaired >= 1
    assert obj.source_file_id is None
    assert any(f["kind"] == "source_object_missing_source_file" for f in report.findings)


@pytest.mark.asyncio
async def test_reconcile_stuck_waiting_ingestion_finishes_when_jobs_done():
    run = SimpleNamespace(
        id="run1",
        status=ConnectorSyncRunStatus.waiting_ingestion.value,
        updated_at=datetime.now(UTC) - timedelta(hours=12),
        finished_at=None,
        deleted_at=None,
    )
    item = SimpleNamespace(
        id="item1",
        sync_run_id="run1",
        ingestion_job_id="job1",
        status=ConnectorSyncItemStatus.waiting_parse.value,
        error=None,
        deleted_at=None,
    )
    job = SimpleNamespace(id="job1", status="active", deleted_at=None)

    async def _get(model, pk):
        if pk == "job1":
            return job
        return None

    db = MagicMock()
    db.get = AsyncMock(side_effect=_get)

    empty = MagicMock()
    empty.scalars.return_value.all.return_value = []
    stuck = MagicMock()
    stuck.scalars.return_value.all.return_value = [run]
    pending = MagicMock()
    pending.scalars.return_value.all.return_value = [item]
    db.execute = AsyncMock(side_effect=[empty, empty, empty, stuck, pending])

    report = await connector_reconciliation_service.reconcile_connector_links(db)
    assert any(f["kind"] == "stuck_waiting_ingestion" for f in report.findings)
    assert run.status == ConnectorSyncRunStatus.completed.value
    assert item.status == ConnectorSyncItemStatus.applied.value

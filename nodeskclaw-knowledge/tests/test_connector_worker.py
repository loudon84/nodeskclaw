"""Connector worker and API-ish service unit tests."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import ConnectorStatus, ConnectorSyncMode, ConnectorSyncRunStatus
from app.schemas.principal import KnowledgePrincipal
from app.services import connector_service
from app.workers import connector_worker


def _member() -> KnowledgePrincipal:
    return KnowledgePrincipal(user_id="u1", member_id="m1", org_id="o1")


def test_validate_sync_interval_min():
    with pytest.raises(Exception) as exc:
        connector_service.validate_sync_settings(ConnectorSyncMode.interval.value, 60)
    assert "connector_interval_too_small" in str(exc.value.message_key)


def test_sanitize_config_rejects_secrets():
    with pytest.raises(Exception) as exc:
        connector_service.sanitize_config("http_manifest", {"manifest_url": "https://x", "api_key": "x"})
    assert "connector_config_invalid" in str(exc.value.message_key)


def test_sanitize_filesystem_config():
    cfg = connector_service.sanitize_config("filesystem", {"root_alias": "docs", "sub_path": "a"})
    assert cfg["root_alias"] == "docs"
    with pytest.raises(Exception):
        connector_service.sanitize_config("filesystem", {"root_alias": "docs", "absolute_path": "/etc"})


@pytest.mark.asyncio
async def test_trigger_sync_returns_pending_run():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    connector = MagicMock()
    connector.id = "c1"
    connector.org_id = "o1"
    connector.knowledge_base_id = "kb1"
    connector.status = ConnectorStatus.active.value
    connector.sync_cursor = None

    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=empty)

    with (
        patch.object(connector_service, "get_connector", AsyncMock(return_value=connector)),
        patch.object(connector_service, "has_kb_permission", AsyncMock(return_value=True)),
        patch.object(connector_service, "write_audit", AsyncMock()),
    ):
        run = await connector_service.trigger_sync(db, _member(), "c1")
    assert run.status == ConnectorSyncRunStatus.pending.value
    assert run.connector_id == "c1"


@pytest.mark.asyncio
async def test_schedule_due_connectors():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    connector = MagicMock()
    connector.id = "c1"
    connector.status = ConnectorStatus.active.value
    connector.sync_mode = ConnectorSyncMode.interval.value
    connector.next_sync_at = datetime.now(UTC) - timedelta(seconds=1)
    connector.sync_interval_seconds = 300
    connector.sync_cursor = None

    due = MagicMock()
    due.scalars.return_value.all.return_value = [connector]
    empty = MagicMock()
    empty.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(side_effect=[due, empty])

    created = await connector_service.schedule_due_connectors(db)
    assert len(created) == 1
    assert connector.next_sync_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_claim_and_process_sync_run():
    db = AsyncMock()
    run = MagicMock()
    run.id = "run1"
    run.connector_id = "c1"
    run.status = ConnectorSyncRunStatus.pending.value

    connector = MagicMock()
    connector.id = "c1"
    connector.deleted_at = None
    connector.config = {"root_alias": "docs"}
    connector.connector_type = "filesystem"

    adapter = AsyncMock()
    adapter.close = AsyncMock()

    db.get = AsyncMock(return_value=connector)
    db.refresh = AsyncMock()
    db.commit = AsyncMock()

    with (
        patch.object(connector_worker.job_leasing, "ownership_matches", return_value=True),
        patch.object(connector_worker.job_leasing, "heartbeat", AsyncMock(return_value=True)),
        patch.object(connector_worker.job_leasing, "clear_lease_if_owner", AsyncMock(return_value=True)),
        patch.object(connector_worker.connector_service, "build_adapter", AsyncMock(return_value=adapter)),
        patch.object(connector_worker.connector_sync_service, "run_sync", AsyncMock(return_value=run)),
        patch.object(connector_worker, "_track_child_ingestion", AsyncMock()),
    ):
        await connector_worker.process_sync_run(
            db, AsyncMock(), run, lease_owner="w1", lease_token="t1"
        )
    adapter.close.assert_awaited()

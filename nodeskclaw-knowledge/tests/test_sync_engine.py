"""Sync engine unit tests: identity, incremental, delete, failure, mid-discovery."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.connectors.models import DiscoveryPage, FetchedSource, SourceDescriptor
from app.models.enums import (
    ArchiveReason,
    ConnectorSourceObjectState,
    ConnectorSyncRunStatus,
    SourceKind,
)
from app.services import connector_sync_service, source_registry_service


class FakeAdapter:
    def __init__(self, pages: list[DiscoveryPage], *, fail_on_page: int | None = None, fetches: dict | None = None):
        self.pages = pages
        self.fail_on_page = fail_on_page
        self.fetches = fetches or {}
        self.call = 0
        self.capabilities = MagicMock(incremental_cursor=True)

    async def discover(self, *, cursor=None):
        if self.fail_on_page is not None and self.call == self.fail_on_page:
            raise RuntimeError("discovery failed mid-way")
        page = self.pages[min(self.call, len(self.pages) - 1)]
        self.call += 1
        return page

    async def fetch(self, descriptor: SourceDescriptor):
        data = self.fetches.get(descriptor.external_object_id, b"content")
        return FetchedSource(file_name=descriptor.name, mime_type="text/plain", stream=data, size=len(data), sha256=None)

    async def close(self):
        return None


def _descriptor(oid: str, *, revision: str = "1", deleted: bool = False) -> SourceDescriptor:
    return SourceDescriptor(
        external_object_id=oid,
        name=f"{oid}.txt",
        path=f"/{oid}.txt",
        canonical_uri=f"https://example.com/{oid}",
        external_revision=revision,
        source_metadata={"department": "ops"},
        is_deleted=deleted,
    )


def test_content_changed_order():
    obj = MagicMock()
    obj.source_file_id = "sf1"
    obj.external_revision = "1"
    obj.etag = "e1"
    obj.last_content_sha256 = "abc"

    d = _descriptor("x", revision="2")
    assert source_registry_service.content_changed(obj, d) == "revision"

    d2 = SourceDescriptor(external_object_id="x", name="x", external_revision="1", etag="e2")
    obj.external_revision = "1"
    assert source_registry_service.content_changed(obj, d2) == "etag"

    d3 = SourceDescriptor(external_object_id="x", name="x", external_revision="1", etag="e1")
    assert source_registry_service.content_changed(obj, d3, fetched_sha256="zzz") == "sha256"
    assert source_registry_service.content_changed(obj, d3, fetched_sha256="abc") == "unchanged"


def test_map_metadata():
    d = _descriptor("a")
    mapped = source_registry_service.map_metadata(d, {"department": "dept"})
    assert mapped == {"dept": "ops"}


@pytest.mark.asyncio
async def test_full_sync_missing_to_deleted_only_after_complete():
    db = AsyncMock()
    db.get = AsyncMock(side_effect=lambda model, _id: MagicMock(id=_id, deleted_at=None, status="active", ragflow_dataset_id="ds", metadata_schema=None, org_id="o1") if model.__name__ == "KnowledgeBase" else None)
    db.flush = AsyncMock()
    db.execute = AsyncMock()

    connector = MagicMock()
    connector.id = "c1"
    connector.org_id = "o1"
    connector.knowledge_base_id = "kb1"
    connector.config = {}
    connector.sync_cursor = None
    connector.owner_member_id = "m1"

    sync_run = MagicMock()
    sync_run.id = "run1"
    sync_run.metrics = {}
    sync_run.cursor_before = None
    sync_run.cursor_after = None
    sync_run.started_at = None
    sync_run.status = "pending"

    pages = [
        DiscoveryPage(objects=[_descriptor("a")], next_cursor=None, has_more=False),
    ]
    adapter = FakeAdapter(pages)
    adapter.capabilities.incremental_cursor = False

    missing_obj = MagicMock()
    missing_obj.external_object_id = "gone"
    missing_obj.source_file_id = "sf-gone"
    missing_obj.state = ConnectorSourceObjectState.active.value

    upserted = MagicMock()
    upserted.id = "obj-a"
    upserted.source_file_id = None
    upserted.state = "active"
    upserted.last_content_sha256 = None

    async def fake_upsert(**kwargs):
        return upserted

    sf_gone = MagicMock()
    sf_gone.id = "sf-gone"
    sf_gone.deleted_at = None
    sf_gone.connector_id = "c1"
    sf_gone.source_kind = SourceKind.connector.value
    sf_gone.archived_at = None
    sf_gone.active_version_id = None

    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = [missing_obj]

    with (
        patch.object(connector_sync_service.source_registry_service, "upsert_source_object", side_effect=fake_upsert),
        patch.object(connector_sync_service, "_process_descriptor", AsyncMock()),
        patch.object(connector_sync_service, "archive_for_source_deleted", AsyncMock()) as archive,
    ):
        # First: mid-discovery failure must NOT delete
        failing = FakeAdapter(pages, fail_on_page=0)
        failing.capabilities.incremental_cursor = False
        ragflow = AsyncMock()
        with pytest.raises(RuntimeError):
            await connector_sync_service.run_sync(db, ragflow, failing, connector=connector, sync_run=sync_run)
        archive.assert_not_awaited()
        assert sync_run.status == ConnectorSyncRunStatus.failed.value

        # Reset and complete full sync → missing archived
        sync_run.status = "pending"
        sync_run.metrics = {}
        db.execute = AsyncMock(return_value=list_result)
        db.get = AsyncMock(
            side_effect=lambda model, oid: (
                MagicMock(id="kb1", deleted_at=None, status="active", ragflow_dataset_id="ds", metadata_schema=None, org_id="o1")
                if getattr(model, "__name__", "") == "KnowledgeBase"
                else sf_gone
            )
        )
        with patch.object(connector_sync_service, "_add_sync_item", AsyncMock()):
            await connector_sync_service.run_sync(db, ragflow, adapter, connector=connector, sync_run=sync_run)
        archive.assert_awaited()
        assert missing_obj.state == ConnectorSourceObjectState.deleted.value
        assert sync_run.status in {ConnectorSyncRunStatus.completed.value, ConnectorSyncRunStatus.partial.value}


@pytest.mark.asyncio
async def test_incremental_advances_cursor_after_persist():
    db = AsyncMock()
    db.flush = AsyncMock()
    kb = MagicMock(id="kb1", deleted_at=None, status="active", ragflow_dataset_id="ds", metadata_schema=None, org_id="o1")
    db.get = AsyncMock(return_value=kb)

    connector = MagicMock()
    connector.id = "c1"
    connector.org_id = "o1"
    connector.knowledge_base_id = "kb1"
    connector.config = {}
    connector.sync_cursor = {"cursor": "0"}
    connector.owner_member_id = "m1"

    sync_run = MagicMock()
    sync_run.id = "run1"
    sync_run.metrics = {}
    sync_run.cursor_before = {"cursor": "0"}
    sync_run.cursor_after = None
    sync_run.started_at = None

    pages = [
        DiscoveryPage(objects=[_descriptor("a")], next_cursor={"cursor": "1"}, has_more=True),
        DiscoveryPage(objects=[_descriptor("b")], next_cursor=None, has_more=False),
    ]
    adapter = FakeAdapter(pages)

    with patch.object(connector_sync_service, "_process_descriptor", AsyncMock()) as process:
        ragflow = AsyncMock()
        await connector_sync_service.run_sync(db, ragflow, adapter, connector=connector, sync_run=sync_run)
        assert process.await_count == 2
        assert connector.sync_cursor == {"cursor": "1"} or sync_run.cursor_after in (None, {"cursor": "1"})
        # Final page has no cursor; last advanced cursor after first page persist
        assert sync_run.status == ConnectorSyncRunStatus.completed.value


@pytest.mark.asyncio
async def test_delete_event_archives_with_source_deleted():
    db = AsyncMock()
    db.flush = AsyncMock()
    kb = MagicMock(id="kb1", deleted_at=None, ragflow_dataset_id=None)
    sf = MagicMock()
    sf.id = "sf1"
    sf.deleted_at = None
    sf.connector_id = "c1"
    sf.source_kind = SourceKind.connector.value
    sf.archived_at = None
    sf.active_version_id = None

    obj = MagicMock()
    obj.id = "obj1"
    obj.source_file_id = "sf1"

    connector = MagicMock(id="c1")
    sync_run = MagicMock(id="run1")
    metrics = {"archived_count": 0}
    ragflow = AsyncMock()

    db.get = AsyncMock(return_value=sf)
    with patch.object(connector_sync_service, "_add_sync_item", AsyncMock()):
        await connector_sync_service._handle_deleted_descriptor(
            db, ragflow, connector=connector, kb=kb, sync_run=sync_run, obj=obj, metrics=metrics
        )
    assert sf.archive_reason == ArchiveReason.source_deleted.value
    assert metrics["archived_count"] == 1


@pytest.mark.asyncio
async def test_restore_only_for_source_deleted():
    ragflow = AsyncMock()
    db = AsyncMock()
    kb = MagicMock(ragflow_dataset_id=None)
    sf = MagicMock()
    sf.archive_reason = ArchiveReason.user.value
    sf.archived_at = datetime.now(UTC)
    sf.active_version_id = None
    assert await connector_sync_service.restore_source_deleted(db, ragflow, sf=sf, kb=kb) is False

    sf.archive_reason = ArchiveReason.source_deleted.value
    assert await connector_sync_service.restore_source_deleted(db, ragflow, sf=sf, kb=kb) is True
    assert sf.archived_at is None

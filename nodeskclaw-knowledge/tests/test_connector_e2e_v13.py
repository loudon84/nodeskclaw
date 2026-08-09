"""E2E-style connector scenarios for PRD §95-99 using mocks/temp dirs."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.connectors.filesystem.connector import FilesystemConnector
from app.connectors.http_manifest.connector import HttpManifestConnector
from app.connectors.models import DiscoveryPage, FetchedSource, SourceDescriptor
from app.models.enums import ConnectorSyncRunStatus, SourceKind
from app.services import connector_sync_service


class TrackingAdapter:
    capabilities = MagicMock(incremental_cursor=True)

    def __init__(self):
        self.fetch_ids: list[str] = []
        self._pages: list[DiscoveryPage] = []

    def set_pages(self, pages: list[DiscoveryPage]):
        self._pages = pages
        self._i = 0

    async def discover(self, *, cursor=None):
        page = self._pages[min(self._i, len(self._pages) - 1)]
        self._i += 1
        return page

    async def fetch(self, descriptor: SourceDescriptor):
        self.fetch_ids.append(descriptor.external_object_id)
        content = descriptor.source_metadata.get("content", b"data")
        if isinstance(content, str):
            content = content.encode()
        return FetchedSource(
            file_name=descriptor.name,
            mime_type="application/pdf",
            stream=content,
            size=len(content),
            sha256=descriptor.source_metadata.get("sha256"),
        )

    async def close(self):
        return None


def _run(connector_id="c1"):
    return MagicMock(
        id="run1",
        connector_id=connector_id,
        status=ConnectorSyncRunStatus.pending.value,
        metrics={},
        started_at=None,
        finished_at=None,
        cursor_before=None,
        cursor_after=None,
        created_by_member_id="m1",
        error_message=None,
        error_code=None,
    )


def _connector():
    return MagicMock(
        id="c1",
        org_id="o1",
        knowledge_base_id="kb1",
        owner_member_id="m1",
        connector_type="filesystem",
        config={},
        sync_cursor=None,
        last_sync_succeeded_at=None,
        last_error=None,
        last_error_code=None,
    )


@pytest.mark.asyncio
async def test_e2e_filesystem_initial_sync_discovers_three(tmp_path: Path):
    root = tmp_path / "product"
    root.mkdir()
    for name in ("A.pdf", "B.pdf", "C.pdf"):
        (root / name).write_bytes(b"%PDF-1.4 " + name.encode())

    fs = FilesystemConnector({"root_alias": "docs"}, roots={"docs": str(root)})
    page = await fs.discover()
    assert {o.name for o in page.objects} == {"A.pdf", "B.pdf", "C.pdf"}
    await fs.close()


def _empty_execute():
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    return result


@pytest.mark.asyncio
async def test_e2e_modify_creates_new_version_path():
    """Content change triggers update_content; identity SourceFile stays."""
    adapter = TrackingAdapter()
    adapter.capabilities = MagicMock(incremental_cursor=False)
    desc = SourceDescriptor(
        external_object_id="A.pdf",
        name="A.pdf",
        path="A.pdf",
        external_revision="2",
        source_metadata={"content": b"v2-content", "sha256": "sha-v2"},
    )
    adapter.set_pages([DiscoveryPage(objects=[desc], has_more=False)])

    existing_sf = MagicMock(
        id="sf-a",
        deleted_at=None,
        archived_at=None,
        source_kind=SourceKind.connector.value,
        connector_id="c1",
        metadata_={},
        metadata_revision=0,
    )
    obj = MagicMock(
        id="so-a",
        source_file_id="sf-a",
        external_object_id="A.pdf",
        external_revision="1",
        etag=None,
        last_content_sha256="sha-v1",
        state="active",
        last_error=None,
    )

    db = AsyncMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(return_value=_empty_execute())
    db.get = AsyncMock(side_effect=lambda model, pk: existing_sf if pk == "sf-a" else MagicMock(id="kb1", deleted_at=None, ragflow_dataset_id="ds1", metadata_schema={}, status="active"))
    ragflow = AsyncMock()
    connector = _connector()
    run = _run()

    with patch(
        "app.services.connector_sync_service.source_registry_service.upsert_source_object",
        new=AsyncMock(return_value=obj),
    ), patch(
        "app.services.connector_sync_service.source_registry_service.content_changed",
        return_value="revision",
    ), patch(
        "app.services.connector_sync_service.ingestion_facade.ingest_from_connector",
        new=AsyncMock(return_value=(existing_sf, MagicMock(id="v2"), MagicMock(id="job1"))),
    ) as ingest, patch(
        "app.services.connector_sync_service.source_registry_service.bind_source_file",
        new=AsyncMock(),
    ), patch(
        "app.services.connector_sync_service.write_audit",
        new=AsyncMock(),
    ), patch(
        "app.services.connector_sync_service.metrics_service.observe_connector_sync",
    ), patch(
        "app.services.connector_sync_service.metrics_service.observe_connector_fetch",
    ):
        await connector_sync_service.run_sync(db, ragflow, adapter, connector=connector, sync_run=run)

    ingest.assert_awaited_once()
    assert "A.pdf" in adapter.fetch_ids
    assert run.status in {ConnectorSyncRunStatus.completed.value, ConnectorSyncRunStatus.partial.value}


@pytest.mark.asyncio
async def test_e2e_noop_same_sha_skips_ingest():
    adapter = TrackingAdapter()
    adapter.capabilities = MagicMock(incremental_cursor=False)
    desc = SourceDescriptor(
        external_object_id="A.pdf",
        name="A.pdf",
        path="A.pdf",
        external_revision="mtime-only",
        source_metadata={"content": b"same", "sha256": "same-sha"},
    )
    adapter.set_pages([DiscoveryPage(objects=[desc], has_more=False)])

    existing_sf = MagicMock(
        id="sf-a",
        deleted_at=None,
        archived_at=None,
        source_kind=SourceKind.connector.value,
        connector_id="c1",
        metadata_={},
        metadata_revision=0,
        source_revision="1",
        source_etag=None,
        source_modified_at=None,
        source_metadata={},
        last_synced_at=None,
        sync_state=None,
        file_name="A.pdf",
        source_path="A.pdf",
        source_uri=None,
    )
    obj = MagicMock(
        id="so-a",
        source_file_id="sf-a",
        external_object_id="A.pdf",
        external_revision="1",
        etag=None,
        last_content_sha256="same-sha",
        state="active",
        last_error=None,
        last_synced_at=None,
    )

    db = AsyncMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(return_value=_empty_execute())
    db.get = AsyncMock(
        side_effect=lambda model, pk: existing_sf
        if pk == "sf-a"
        else MagicMock(id="kb1", deleted_at=None, ragflow_dataset_id="ds1", metadata_schema={}, status="active")
    )
    ragflow = AsyncMock()
    connector = _connector()
    run = _run()

    with patch(
        "app.services.connector_sync_service.source_registry_service.upsert_source_object",
        new=AsyncMock(return_value=obj),
    ), patch(
        "app.services.connector_sync_service.source_registry_service.content_changed",
        return_value="revision",
    ), patch(
        "app.services.connector_sync_service.ingestion_facade.ingest_from_connector",
        new=AsyncMock(),
    ) as ingest, patch(
        "app.services.connector_sync_service.write_audit",
        new=AsyncMock(),
    ), patch(
        "app.services.connector_sync_service.metrics_service.observe_connector_sync",
    ), patch(
        "app.services.connector_sync_service.metrics_service.observe_connector_fetch",
    ):
        await connector_sync_service.run_sync(db, ragflow, adapter, connector=connector, sync_run=run)

    ingest.assert_not_awaited()
    assert run.metrics["unchanged_count"] >= 1


@pytest.mark.asyncio
async def test_e2e_delete_archives_source():
    adapter = TrackingAdapter()
    adapter.set_pages([DiscoveryPage(objects=[], has_more=False)])
    missing_obj = MagicMock(
        id="so-b",
        external_object_id="B.pdf",
        source_file_id="sf-b",
        state="active",
    )
    sf = MagicMock(
        id="sf-b",
        deleted_at=None,
        source_kind=SourceKind.connector.value,
        connector_id="c1",
        archived_at=None,
        active_version_id=None,
        sync_state=None,
        archive_reason=None,
    )

    db = AsyncMock()
    db.flush = AsyncMock()
    db.get = AsyncMock(
        side_effect=lambda model, pk: sf
        if pk == "sf-b"
        else MagicMock(id="kb1", deleted_at=None, ragflow_dataset_id="ds1", metadata_schema={}, status="active")
    )

    active_objs = MagicMock()
    active_objs.scalars.return_value.all.return_value = [missing_obj]
    db.execute = AsyncMock(return_value=active_objs)

    ragflow = AsyncMock()
    connector = _connector()
    run = _run()

    with patch(
        "app.services.connector_sync_service.write_audit",
        new=AsyncMock(),
    ), patch(
        "app.services.connector_sync_service.metrics_service.observe_connector_sync",
    ):
        await connector_sync_service.run_sync(db, ragflow, adapter, connector=connector, sync_run=run)

    assert missing_obj.state == "deleted"
    assert sf.archived_at is not None
    assert run.metrics["archived_count"] >= 1


@pytest.mark.asyncio
async def test_e2e_http_incremental_only_processes_changed():
    adapter = TrackingAdapter()
    changed = [
        SourceDescriptor(external_object_id=f"doc-{i}", name=f"{i}.txt", external_revision="2", source_metadata={"content": b"x", "sha256": f"sha-{i}"})
        for i in range(3)
    ]
    deleted = SourceDescriptor(external_object_id="doc-del", name="del.txt", is_deleted=True)
    unchanged = [
        SourceDescriptor(external_object_id=f"keep-{i}", name=f"k{i}.txt", external_revision="1")
        for i in range(2)
    ]
    adapter.set_pages([DiscoveryPage(objects=changed + [deleted] + unchanged, has_more=False)])
    adapter.capabilities = MagicMock(incremental_cursor=True)

    objs = {}

    async def upsert(db, **kwargs):
        d = kwargs["descriptor"]
        if d.external_object_id not in objs:
            objs[d.external_object_id] = MagicMock(
                id=f"so-{d.external_object_id}",
                source_file_id=None if d.external_object_id.startswith("doc-") and d.external_object_id != "doc-del" else f"sf-{d.external_object_id}",
                external_revision="1",
                etag=None,
                last_content_sha256="same" if d.external_object_id.startswith("keep-") else None,
                state="active",
                last_error=None,
                last_synced_at=None,
            )
        return objs[d.external_object_id]

    def content_changed(obj, descriptor, fetched_sha256=None):
        if descriptor.external_object_id.startswith("keep-"):
            return "unchanged"
        return "revision"

    def _sf_for(pk):
        if not str(pk).startswith("sf-"):
            return MagicMock(id="kb1", deleted_at=None, ragflow_dataset_id="ds1", metadata_schema={}, status="active")
        return MagicMock(
            id=pk,
            deleted_at=None,
            archived_at=None if pk != "sf-doc-del" else None,
            source_kind=SourceKind.connector.value,
            connector_id="c1",
            metadata_={},
            metadata_revision=0,
            source_revision="1",
            source_etag=None,
            source_modified_at=None,
            source_metadata={},
            last_synced_at=None,
            sync_state=None,
            file_name=pk,
            source_path=pk,
            source_uri=None,
            active_version_id=None,
        )

    db = AsyncMock()
    db.flush = AsyncMock()
    db.get = AsyncMock(side_effect=lambda model, pk: _sf_for(pk))
    ragflow = AsyncMock()
    connector = _connector()
    connector.connector_type = "http_manifest"
    connector.sync_cursor = {"cursor": "prev"}
    run = _run()
    run.cursor_before = {"cursor": "prev"}

    with patch(
        "app.services.connector_sync_service.source_registry_service.upsert_source_object",
        new=AsyncMock(side_effect=upsert),
    ), patch(
        "app.services.connector_sync_service.source_registry_service.content_changed",
        side_effect=content_changed,
    ), patch(
        "app.services.connector_sync_service.ingestion_facade.ingest_from_connector",
        new=AsyncMock(return_value=(MagicMock(id="sf-new"), MagicMock(id="v"), MagicMock(id="job"))),
    ) as ingest, patch(
        "app.services.connector_sync_service.source_registry_service.bind_source_file",
        new=AsyncMock(),
    ), patch(
        "app.services.connector_sync_service.write_audit",
        new=AsyncMock(),
    ), patch(
        "app.services.connector_sync_service.metrics_service.observe_connector_sync",
    ), patch(
        "app.services.connector_sync_service.metrics_service.observe_connector_fetch",
    ), patch(
        "app.services.connector_sync_service.archive_for_source_deleted",
        new=AsyncMock(),
    ):
        await connector_sync_service.run_sync(db, ragflow, adapter, connector=connector, sync_run=run)

    assert ingest.await_count == 3
    assert set(adapter.fetch_ids) == {"doc-0", "doc-1", "doc-2"}


def test_http_manifest_still_registered():
    assert HttpManifestConnector

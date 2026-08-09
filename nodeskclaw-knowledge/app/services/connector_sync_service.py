"""Connector sync engine: full/incremental discovery, change detection, apply."""

from __future__ import annotations

import io
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import KnowledgeSourceConnector
from app.connectors.models import SourceDescriptor
from app.core.exceptions import BadRequestError
from app.integrations.ragflow.client import RagflowClient
from app.models.base import not_deleted
from app.models.connector import (
    ConnectorSourceObject,
    ConnectorSyncItem,
    ConnectorSyncRun,
    KnowledgeSourceConnector as ConnectorRow,
)
from app.models.enums import (
    ArchiveReason,
    ConnectorSourceObjectState,
    ConnectorSyncItemAction,
    ConnectorSyncItemStatus,
    ConnectorSyncRunStatus,
    SourceKind,
    SourceSyncState,
)
from app.models.knowledge_base import KnowledgeBase
from app.models.source_file import SourceFile
from app.models.source_file_version import SourceFileVersion
from app.services import ingestion_facade, source_registry_service
from app.services.ingestion_facade import actor_from_connector
from app.services.metadata_service import validate_metadata_values

logger = logging.getLogger(__name__)

# @lat: [[knowledge-objects#Connector Domain]]


def _now() -> datetime:
    return datetime.now(UTC)


def _default_metrics() -> dict[str, Any]:
    return {
        "discovered_count": 0,
        "unchanged_count": 0,
        "created_count": 0,
        "updated_count": 0,
        "archived_count": 0,
        "restored_count": 0,
        "failed_count": 0,
        "fetch_count": 0,
        "ingestion_dispatched_count": 0,
    }


async def _add_sync_item(
    db: AsyncSession,
    *,
    sync_run_id: str,
    action: str,
    source_object_id: str | None = None,
    source_file_id: str | None = None,
    status: str = ConnectorSyncItemStatus.pending.value,
    ingestion_job_id: str | None = None,
    error: str | None = None,
    details: dict[str, Any] | None = None,
) -> ConnectorSyncItem:
    item = ConnectorSyncItem(
        sync_run_id=sync_run_id,
        source_object_id=source_object_id,
        source_file_id=source_file_id,
        action=action,
        status=status,
        ingestion_job_id=ingestion_job_id,
        error=error,
        details=details or {},
    )
    db.add(item)
    await db.flush()
    return item


async def archive_for_source_deleted(
    db: AsyncSession,
    ragflow: RagflowClient,
    *,
    sf: SourceFile,
    kb: KnowledgeBase,
) -> None:
    if sf.archived_at is None:
        sf.archived_at = _now()
    sf.archive_reason = ArchiveReason.source_deleted.value
    sf.sync_state = SourceSyncState.stale.value
    if kb.ragflow_dataset_id and sf.active_version_id:
        version = await db.get(SourceFileVersion, sf.active_version_id)
        if version and version.ragflow_document_id and version.deleted_at is None:
            try:
                await ragflow.set_document_enabled(kb.ragflow_dataset_id, version.ragflow_document_id, False)
            except Exception:
                logger.warning("disable archived document failed source_file_id=%s", sf.id)


async def restore_source_deleted(
    db: AsyncSession,
    ragflow: RagflowClient,
    *,
    sf: SourceFile,
    kb: KnowledgeBase,
) -> bool:
    if sf.archive_reason != ArchiveReason.source_deleted.value:
        return False
    sf.archived_at = None
    sf.archive_reason = None
    sf.sync_state = SourceSyncState.in_sync.value
    if kb.ragflow_dataset_id and sf.active_version_id:
        version = await db.get(SourceFileVersion, sf.active_version_id)
        if version and version.ragflow_document_id and version.deleted_at is None:
            try:
                await ragflow.set_document_enabled(kb.ragflow_dataset_id, version.ragflow_document_id, True)
            except Exception:
                logger.warning("enable restored document failed source_file_id=%s", sf.id)
    return True


async def apply_rename_or_path(
    sf: SourceFile,
    descriptor: SourceDescriptor,
) -> bool:
    changed = False
    if descriptor.name and sf.file_name != descriptor.name:
        sf.file_name = descriptor.name
        changed = True
    path = descriptor.path or descriptor.name
    if path and sf.source_path != path:
        sf.source_path = path
        changed = True
    if descriptor.canonical_uri and sf.source_uri != descriptor.canonical_uri:
        sf.source_uri = descriptor.canonical_uri
        changed = True
    return changed


async def run_sync(
    db: AsyncSession,
    ragflow: RagflowClient,
    adapter: KnowledgeSourceConnector,
    *,
    connector: ConnectorRow,
    sync_run: ConnectorSyncRun,
) -> ConnectorSyncRun:
    kb = await db.get(KnowledgeBase, connector.knowledge_base_id)
    if kb is None or kb.deleted_at is not None:
        raise BadRequestError(message="知识库不存在", message_key="errors.knowledge.kb_not_found")

    metrics = dict(sync_run.metrics or _default_metrics())
    for key, value in _default_metrics().items():
        metrics.setdefault(key, value)

    sync_run.status = ConnectorSyncRunStatus.discovering.value
    sync_run.started_at = sync_run.started_at or _now()
    await db.flush()

    seen_ids: set[str] = set()
    cursor = dict(sync_run.cursor_before or connector.sync_cursor or {}) or None
    discovery_complete = False
    last_cursor_after: dict[str, Any] | None = None
    incremental = bool(getattr(adapter.capabilities, "incremental_cursor", False) and cursor)

    try:
        while True:
            page = await adapter.discover(cursor=cursor)
            for descriptor in page.objects:
                seen_ids.add(descriptor.external_object_id)
                metrics["discovered_count"] += 1
                await _process_descriptor(
                    db,
                    ragflow,
                    adapter,
                    connector=connector,
                    kb=kb,
                    sync_run=sync_run,
                    descriptor=descriptor,
                    metrics=metrics,
                )
            if page.next_cursor:
                # Persist after applying page, then advance cursor (incremental safety)
                last_cursor_after = dict(page.next_cursor)
                sync_run.cursor_after = last_cursor_after
                if incremental:
                    connector.sync_cursor = last_cursor_after
                await db.flush()
                cursor = last_cursor_after
            if not page.has_more:
                discovery_complete = True
                break

        sync_run.status = ConnectorSyncRunStatus.applying.value
        await db.flush()

        # Missing → deleted only after complete discovery on full sync (no prior cursor)
        if discovery_complete and not incremental:
            await _mark_missing_as_deleted(
                db,
                ragflow,
                connector=connector,
                kb=kb,
                sync_run=sync_run,
                seen_ids=seen_ids,
                metrics=metrics,
            )

        sync_run.metrics = metrics
        sync_run.cursor_after = last_cursor_after if last_cursor_after is not None else sync_run.cursor_after
        if discovery_complete and last_cursor_after is None and not incremental:
            # Full sync without cursor: clear incremental cursor
            connector.sync_cursor = None
        if metrics["failed_count"] > 0:
            sync_run.status = ConnectorSyncRunStatus.partial.value
        else:
            sync_run.status = ConnectorSyncRunStatus.completed.value
        sync_run.finished_at = _now()
        connector.last_sync_succeeded_at = sync_run.finished_at
        connector.last_error = None
        connector.last_error_code = None
        await db.flush()
        return sync_run
    except Exception as exc:
        sync_run.status = ConnectorSyncRunStatus.failed.value
        sync_run.error_message = str(exc)
        sync_run.error_code = "errors.knowledge.connector_sync_failed"
        sync_run.finished_at = _now()
        sync_run.metrics = metrics
        connector.last_error = str(exc)
        connector.last_error_code = sync_run.error_code
        await db.flush()
        raise


async def _process_descriptor(
    db: AsyncSession,
    ragflow: RagflowClient,
    adapter: KnowledgeSourceConnector,
    *,
    connector: ConnectorRow,
    kb: KnowledgeBase,
    sync_run: ConnectorSyncRun,
    descriptor: SourceDescriptor,
    metrics: dict[str, Any],
) -> None:
    obj = await source_registry_service.upsert_source_object(
        db,
        connector_id=connector.id,
        descriptor=descriptor,
        sync_run_id=sync_run.id,
    )

    if descriptor.is_deleted:
        await _handle_deleted_descriptor(db, ragflow, connector=connector, kb=kb, sync_run=sync_run, obj=obj, metrics=metrics)
        return

    sf: SourceFile | None = None
    if obj.source_file_id:
        sf = await db.get(SourceFile, obj.source_file_id)
        if sf and sf.deleted_at is not None:
            sf = None
            obj.source_file_id = None

    # Restore if previously archived due to source_deleted
    if sf and sf.archived_at is not None:
        restored = await restore_source_deleted(db, ragflow, sf=sf, kb=kb)
        if restored:
            metrics["restored_count"] += 1
            await _add_sync_item(
                db,
                sync_run_id=sync_run.id,
                action=ConnectorSyncItemAction.restore.value,
                source_object_id=obj.id,
                source_file_id=sf.id,
                status=ConnectorSyncItemStatus.applied.value,
            )
        else:
            # User-archived: skip
            metrics["unchanged_count"] += 1
            return

    change = source_registry_service.content_changed(obj, descriptor)
    if change == "unchanged" and sf is not None:
        # Still allow rename/path/metadata-only updates without reparse
        renamed = await apply_rename_or_path(sf, descriptor)
        mapped = source_registry_service.map_metadata(descriptor, (connector.config or {}).get("metadata_mapping"))
        meta_changed = False
        if mapped:
            try:
                merged = {**(sf.metadata_ or {}), **mapped}
                validated = validate_metadata_values(merged, kb.metadata_schema, partial=False)
                if validated != (sf.metadata_ or {}):
                    sf.metadata_ = validated
                    sf.metadata_revision = int(sf.metadata_revision or 0) + 1
                    meta_changed = True
            except Exception as exc:
                metrics["failed_count"] += 1
                obj.last_error = str(exc)
                obj.state = ConnectorSourceObjectState.error.value
                await _add_sync_item(
                    db,
                    sync_run_id=sync_run.id,
                    action=ConnectorSyncItemAction.update_metadata.value,
                    source_object_id=obj.id,
                    source_file_id=sf.id,
                    status=ConnectorSyncItemStatus.failed.value,
                    error=str(exc),
                )
                return
        if renamed or meta_changed:
            sf.source_revision = descriptor.external_revision or sf.source_revision
            sf.source_etag = descriptor.etag or sf.source_etag
            sf.source_modified_at = descriptor.modified_at or sf.source_modified_at
            sf.source_metadata = dict(descriptor.source_metadata or {})
            sf.last_synced_at = _now()
            sf.sync_state = SourceSyncState.in_sync.value
            obj.external_revision = descriptor.external_revision
            obj.etag = descriptor.etag
            obj.last_synced_at = _now()
            metrics["updated_count"] += 1
            await _add_sync_item(
                db,
                sync_run_id=sync_run.id,
                action=ConnectorSyncItemAction.update_metadata.value,
                source_object_id=obj.id,
                source_file_id=sf.id,
                status=ConnectorSyncItemStatus.applied.value,
                details={"renamed": renamed, "metadata": meta_changed},
            )
        else:
            sf.last_synced_at = _now()
            sf.sync_state = SourceSyncState.in_sync.value
            obj.last_synced_at = _now()
            metrics["unchanged_count"] += 1
        return

    # Fetch content for new/changed
    item = await _add_sync_item(
        db,
        sync_run_id=sync_run.id,
        action=ConnectorSyncItemAction.create.value if sf is None else ConnectorSyncItemAction.update_content.value,
        source_object_id=obj.id,
        source_file_id=sf.id if sf else None,
        status=ConnectorSyncItemStatus.fetching.value,
    )
    try:
        fetched = await adapter.fetch(descriptor)
        metrics["fetch_count"] += 1
        stream = fetched.stream
        if isinstance(stream, (bytes, bytearray)):
            content = bytes(stream)
            file_obj = None
            size = fetched.size or len(content)
            digest = fetched.sha256
        else:
            # file-like
            data = stream.read() if hasattr(stream, "read") else b""
            content = data if isinstance(data, (bytes, bytearray)) else b""
            file_obj = io.BytesIO(content)
            size = fetched.size or len(content)
            digest = fetched.sha256

        if not digest and content:
            import hashlib

            digest = hashlib.sha256(content).hexdigest()

        # Unchanged after fetch (revision hint != content authority)
        if sf is not None and digest and obj.last_content_sha256 and digest == obj.last_content_sha256:
            sf.source_revision = descriptor.external_revision
            sf.source_etag = descriptor.etag
            sf.source_modified_at = descriptor.modified_at
            sf.source_metadata = dict(descriptor.source_metadata or {})
            sf.last_synced_at = _now()
            sf.sync_state = SourceSyncState.in_sync.value
            await apply_rename_or_path(sf, descriptor)
            obj.external_revision = descriptor.external_revision
            obj.etag = descriptor.etag
            obj.last_synced_at = _now()
            item.action = ConnectorSyncItemAction.update_metadata.value
            item.status = ConnectorSyncItemStatus.applied.value
            metrics["unchanged_count"] += 1
            return

        mapped = source_registry_service.map_metadata(descriptor, (connector.config or {}).get("metadata_mapping"))
        metadata = None
        if mapped:
            try:
                base = dict(sf.metadata_ or {}) if sf else {}
                metadata = validate_metadata_values({**base, **mapped}, kb.metadata_schema, partial=False)
            except Exception as exc:
                item.status = ConnectorSyncItemStatus.failed.value
                item.error = str(exc)
                metrics["failed_count"] += 1
                obj.state = ConnectorSourceObjectState.error.value
                obj.last_error = str(exc)
                return

        actor = actor_from_connector(connector_id=connector.id, org_id=connector.org_id)
        sf2, version, job = await ingestion_facade.ingest_from_connector(
            db,
            ragflow,
            actor=actor,
            kb=kb,
            file_name=fetched.file_name or descriptor.name,
            mime_type=fetched.mime_type or descriptor.mime_type,
            content=content if file_obj is None else None,
            file_obj=file_obj,
            file_size=size,
            sha256=digest,
            source_file_id=sf.id if sf else None,
            metadata=metadata,
            connector_id=connector.id,
            external_object_id=descriptor.external_object_id,
            source_uri=descriptor.canonical_uri,
            source_path=descriptor.path,
            source_revision=descriptor.external_revision,
            source_etag=descriptor.etag,
            source_modified_at=descriptor.modified_at,
            source_metadata=descriptor.source_metadata,
            owner_member_id=connector.owner_member_id,
        )
        await source_registry_service.bind_source_file(db, obj, sf2)
        obj.last_content_sha256 = digest
        obj.last_synced_at = _now()
        obj.last_error = None
        obj.state = ConnectorSourceObjectState.active.value
        item.source_file_id = sf2.id
        item.ingestion_job_id = job.id
        item.status = ConnectorSyncItemStatus.ingestion_dispatched.value
        metrics["ingestion_dispatched_count"] += 1
        if sf is None:
            metrics["created_count"] += 1
        else:
            metrics["updated_count"] += 1
        del version  # kept for clarity of ingest return
    except Exception as exc:
        item.status = ConnectorSyncItemStatus.failed.value
        item.error = str(exc)
        metrics["failed_count"] += 1
        obj.state = ConnectorSourceObjectState.error.value
        obj.last_error = str(exc)
        logger.exception("sync item failed connector_id=%s external_id=%s", connector.id, descriptor.external_object_id)


async def _handle_deleted_descriptor(
    db: AsyncSession,
    ragflow: RagflowClient,
    *,
    connector: ConnectorRow,
    kb: KnowledgeBase,
    sync_run: ConnectorSyncRun,
    obj: ConnectorSourceObject,
    metrics: dict[str, Any],
) -> None:
    obj.state = ConnectorSourceObjectState.deleted.value
    if not obj.source_file_id:
        return
    sf = await db.get(SourceFile, obj.source_file_id)
    if sf is None or sf.deleted_at is not None:
        return
    if sf.source_kind != SourceKind.connector.value or sf.connector_id != connector.id:
        return
    await archive_for_source_deleted(db, ragflow, sf=sf, kb=kb)
    metrics["archived_count"] += 1
    await _add_sync_item(
        db,
        sync_run_id=sync_run.id,
        action=ConnectorSyncItemAction.archive.value,
        source_object_id=obj.id,
        source_file_id=sf.id,
        status=ConnectorSyncItemStatus.applied.value,
    )


async def _mark_missing_as_deleted(
    db: AsyncSession,
    ragflow: RagflowClient,
    *,
    connector: ConnectorRow,
    kb: KnowledgeBase,
    sync_run: ConnectorSyncRun,
    seen_ids: set[str],
    metrics: dict[str, Any],
) -> None:
    result = await db.execute(
        select(ConnectorSourceObject).where(
            ConnectorSourceObject.connector_id == connector.id,
            ConnectorSourceObject.state == ConnectorSourceObjectState.active.value,
            not_deleted(ConnectorSourceObject),
        )
    )
    for obj in result.scalars().all():
        if obj.external_object_id in seen_ids:
            continue
        obj.state = ConnectorSourceObjectState.missing.value
        obj.state = ConnectorSourceObjectState.deleted.value
        if obj.source_file_id:
            sf = await db.get(SourceFile, obj.source_file_id)
            if sf and sf.deleted_at is None and sf.connector_id == connector.id:
                await archive_for_source_deleted(db, ragflow, sf=sf, kb=kb)
                metrics["archived_count"] += 1
                await _add_sync_item(
                    db,
                    sync_run_id=sync_run.id,
                    action=ConnectorSyncItemAction.archive.value,
                    source_object_id=obj.id,
                    source_file_id=sf.id,
                    status=ConnectorSyncItemStatus.applied.value,
                    details={"reason": "missing_after_full_discovery"},
                )

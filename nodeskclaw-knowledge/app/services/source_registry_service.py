"""Upsert ConnectorSourceObject and map to SourceFile identity."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.models import SourceDescriptor
from app.models.base import not_deleted
from app.models.connector import ConnectorSourceObject
from app.models.enums import ConnectorSourceObjectState
from app.models.source_file import SourceFile


def _now() -> datetime:
    return datetime.now(UTC)


async def get_by_external_id(
    db: AsyncSession,
    *,
    connector_id: str,
    external_object_id: str,
) -> ConnectorSourceObject | None:
    result = await db.execute(
        select(ConnectorSourceObject).where(
            ConnectorSourceObject.connector_id == connector_id,
            ConnectorSourceObject.external_object_id == external_object_id,
            not_deleted(ConnectorSourceObject),
        )
    )
    return result.scalar_one_or_none()


async def upsert_source_object(
    db: AsyncSession,
    *,
    connector_id: str,
    descriptor: SourceDescriptor,
    sync_run_id: str | None = None,
) -> ConnectorSourceObject:
    row = await get_by_external_id(
        db,
        connector_id=connector_id,
        external_object_id=descriptor.external_object_id,
    )
    if row is None:
        row = ConnectorSourceObject(
            connector_id=connector_id,
            external_object_id=descriptor.external_object_id,
            state=ConnectorSourceObjectState.active.value,
        )
        db.add(row)
    row.canonical_uri = descriptor.canonical_uri
    row.display_path = descriptor.path or descriptor.name
    row.external_revision = descriptor.external_revision
    row.etag = descriptor.etag
    row.source_modified_at = descriptor.modified_at
    row.source_metadata = dict(descriptor.source_metadata or {})
    row.last_seen_at = _now()
    if sync_run_id:
        row.last_seen_sync_run_id = sync_run_id
    if descriptor.is_deleted:
        row.state = ConnectorSourceObjectState.deleted.value
    elif row.state in {
        ConnectorSourceObjectState.missing.value,
        ConnectorSourceObjectState.deleted.value,
        ConnectorSourceObjectState.error.value,
    }:
        row.state = ConnectorSourceObjectState.active.value
    await db.flush()
    return row


async def bind_source_file(db: AsyncSession, obj: ConnectorSourceObject, sf: SourceFile) -> None:
    obj.source_file_id = sf.id
    await db.flush()


async def list_active_objects(db: AsyncSession, *, connector_id: str) -> list[ConnectorSourceObject]:
    result = await db.execute(
        select(ConnectorSourceObject).where(
            ConnectorSourceObject.connector_id == connector_id,
            ConnectorSourceObject.state == ConnectorSourceObjectState.active.value,
            not_deleted(ConnectorSourceObject),
        )
    )
    return list(result.scalars().all())


def content_changed(
    obj: ConnectorSourceObject,
    descriptor: SourceDescriptor,
    *,
    fetched_sha256: str | None = None,
) -> str:
    """Return detection result: unchanged | revision | etag | sha256 | new."""
    if obj.source_file_id is None:
        return "new"
    if descriptor.external_revision and obj.external_revision and descriptor.external_revision != obj.external_revision:
        return "revision"
    if descriptor.etag and obj.etag and descriptor.etag != obj.etag:
        return "etag"
    if fetched_sha256 and obj.last_content_sha256 and fetched_sha256 != obj.last_content_sha256:
        return "sha256"
    if fetched_sha256 and not obj.last_content_sha256:
        return "sha256"
    if descriptor.external_revision and not obj.external_revision:
        return "revision"
    if descriptor.etag and not obj.etag:
        return "etag"
    return "unchanged"


def map_metadata(descriptor: SourceDescriptor, mapping: dict[str, Any] | None) -> dict[str, Any]:
    if not mapping:
        return {}
    src = descriptor.source_metadata or {}
    out: dict[str, Any] = {}
    for source_key, target_key in mapping.items():
        if source_key in src and target_key:
            out[str(target_key)] = src[source_key]
    return out

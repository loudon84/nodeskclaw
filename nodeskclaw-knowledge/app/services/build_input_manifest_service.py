"""Corpus input manifest — canonical hash over ACTIVE source files."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.models.enums import SourceFileStatus
from app.models.knowledge_base import KnowledgeBase
from app.models.source_file import SourceFile
from app.models.source_file_version import SourceFileVersion


@dataclass(frozen=True)
class ManifestItem:
    source_file_id: str
    file_version_id: str
    metadata_revision: int
    ragflow_document_id: str

    def to_canonical(self) -> dict[str, Any]:
        return {
            "file_version_id": self.file_version_id,
            "metadata_revision": self.metadata_revision,
            "ragflow_document_id": self.ragflow_document_id,
            "source_file_id": self.source_file_id,
        }


def _canonical_json(items: list[ManifestItem]) -> str:
    payload = [item.to_canonical() for item in sorted(items, key=lambda row: row.source_file_id)]
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def hash_manifest_items(items: list[ManifestItem]) -> str:
    return hashlib.sha256(_canonical_json(items).encode("utf-8")).hexdigest()


def manifest_summary(items: list[ManifestItem]) -> dict[str, Any]:
    return {
        "item_count": len(items),
        "items": [item.to_canonical() for item in sorted(items, key=lambda row: row.source_file_id)],
    }


async def compute_manifest(
    db: AsyncSession,
    kb: KnowledgeBase,
) -> tuple[str, list[ManifestItem], dict[str, Any]]:
    result = await db.execute(
        select(SourceFile, SourceFileVersion)
        .join(SourceFileVersion, SourceFileVersion.id == SourceFile.active_version_id)
        .where(
            SourceFile.knowledge_base_id == kb.id,
            SourceFile.status == SourceFileStatus.active.value,
            SourceFile.active_version_id.is_not(None),
            SourceFileVersion.ragflow_document_id.is_not(None),
            not_deleted(SourceFile),
            not_deleted(SourceFileVersion),
        )
        .order_by(SourceFile.id.asc())
    )
    items: list[ManifestItem] = []
    for sf, version in result.all():
        if not version.ragflow_document_id:
            continue
        items.append(
            ManifestItem(
                source_file_id=sf.id,
                file_version_id=version.id,
                metadata_revision=int(sf.metadata_revision or 0),
                ragflow_document_id=version.ragflow_document_id,
            )
        )
    summary = manifest_summary(items)
    return hash_manifest_items(items), items, summary


def items_from_summary(summary: dict[str, Any] | None) -> list[ManifestItem]:
    if not summary:
        return []
    raw_items = summary.get("items") or []
    items: list[ManifestItem] = []
    for row in raw_items:
        if not isinstance(row, dict):
            continue
        source_file_id = row.get("source_file_id")
        file_version_id = row.get("file_version_id")
        ragflow_document_id = row.get("ragflow_document_id")
        if not source_file_id or not file_version_id or not ragflow_document_id:
            continue
        items.append(
            ManifestItem(
                source_file_id=str(source_file_id),
                file_version_id=str(file_version_id),
                metadata_revision=int(row.get("metadata_revision") or 0),
                ragflow_document_id=str(ragflow_document_id),
            )
        )
    return items


@dataclass
class BuildDelta:
    added: list[ManifestItem]
    changed: list[ManifestItem]
    removed: list[ManifestItem]
    unchanged: list[ManifestItem]

    @property
    def changed_source_file_ids(self) -> set[str]:
        return {item.source_file_id for item in self.added + self.changed}

    def to_summary(self) -> dict[str, int]:
        return {
            "added": len(self.added),
            "changed": len(self.changed),
            "removed": len(self.removed),
            "unchanged": len(self.unchanged),
        }


def compute_build_delta(
    previous: list[ManifestItem],
    current: list[ManifestItem],
) -> BuildDelta:
    prev_map = {item.source_file_id: item for item in previous}
    curr_map = {item.source_file_id: item for item in current}
    added: list[ManifestItem] = []
    changed: list[ManifestItem] = []
    removed: list[ManifestItem] = []
    unchanged: list[ManifestItem] = []
    for source_file_id, curr in curr_map.items():
        prev = prev_map.get(source_file_id)
        if prev is None:
            added.append(curr)
        elif prev != curr:
            changed.append(curr)
        else:
            unchanged.append(curr)
    for source_file_id, prev in prev_map.items():
        if source_file_id not in curr_map:
            removed.append(prev)
    return BuildDelta(added=added, changed=changed, removed=removed, unchanged=unchanged)

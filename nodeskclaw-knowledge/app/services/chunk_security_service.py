"""Chunk security cleaner with active-version and metadata checks."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.ragflow.client import RagflowClient
from app.integrations.ragflow.models import RagflowChunk
from app.models.base import not_deleted
from app.models.enums import ParseStatus
from app.models.source_file import SourceFile
from app.models.source_file_version import SourceFileVersion

logger = logging.getLogger(__name__)


# @lat: [[knowledge#Active Version Security]]
@dataclass
class ActiveDocumentIdentity:
    source_file_id: str
    file_version_id: str
    knowledge_base_id: str
    org_id: str
    active_version_id: str | None


async def clean_chunks(
    db: AsyncSession,
    ragflow: RagflowClient,
    chunks: list[RagflowChunk],
    *,
    allowed_source_file_ids: set[str],
    dataset_id_by_document: dict[str, str] | None = None,
) -> tuple[list[RagflowChunk], int]:
    if not chunks:
        return [], 0

    document_ids = [c.document_id for c in chunks if c.document_id]
    identity_map = await _build_active_document_map(db, document_ids)

    safe: list[RagflowChunk] = []
    filtered = 0
    doc_meta_cache: dict[str, dict] = {}

    for chunk in chunks:
        reason = _evaluate_chunk(
            chunk,
            allowed_source_file_ids=allowed_source_file_ids,
            identity_map=identity_map,
            doc_meta_cache=doc_meta_cache,
            dataset_id_by_document=dataset_id_by_document,
        )
        if reason:
            filtered += 1
            if reason == "unknown":
                logger.warning("drop unknown document chunk_id=%s document_id=%s", chunk.id, chunk.document_id)
            elif reason == "metadata_mismatch":
                logger.warning("drop metadata mismatch chunk_id=%s document_id=%s", chunk.id, chunk.document_id)
            elif reason == "superseded":
                logger.warning("drop superseded chunk_id=%s document_id=%s", chunk.id, chunk.document_id)
            continue
        safe.append(chunk)

    return safe, filtered


def _evaluate_chunk(
    chunk: RagflowChunk,
    *,
    allowed_source_file_ids: set[str],
    identity_map: dict[str, ActiveDocumentIdentity],
    doc_meta_cache: dict[str, dict],
    dataset_id_by_document: dict[str, str] | None,
) -> str | None:
    meta = chunk.document_metadata or {}
    source_file_id = meta.get("nk_source_file_id")
    file_version_id = meta.get("nk_file_version_id")

    if not source_file_id and chunk.document_id:
        if chunk.document_id in doc_meta_cache:
            cached = doc_meta_cache[chunk.document_id]
            source_file_id = cached.get("nk_source_file_id")
            file_version_id = cached.get("nk_file_version_id")
        elif chunk.document_id in identity_map:
            identity = identity_map[chunk.document_id]
            source_file_id = identity.source_file_id
            file_version_id = identity.file_version_id

    if not chunk.document_id or chunk.document_id not in identity_map:
        return "unknown"

    identity = identity_map[chunk.document_id]
    if identity.active_version_id and identity.file_version_id != identity.active_version_id:
        return "superseded"

    if not source_file_id:
        source_file_id = identity.source_file_id
    if not file_version_id:
        file_version_id = identity.file_version_id

    if source_file_id != identity.source_file_id or file_version_id != identity.file_version_id:
        return "metadata_mismatch"

    if source_file_id not in allowed_source_file_ids:
        return "unauthorized"

    chunk.document_metadata = {
        **meta,
        "nk_source_file_id": source_file_id,
        "nk_file_version_id": file_version_id,
        "nk_knowledge_base_id": identity.knowledge_base_id,
        "nk_org_id": identity.org_id,
    }
    return None


async def _build_active_document_map(
    db: AsyncSession,
    document_ids: list[str],
) -> dict[str, ActiveDocumentIdentity]:
    if not document_ids:
        return {}

    result = await db.execute(
        select(SourceFileVersion, SourceFile)
        .join(SourceFile, SourceFile.id == SourceFileVersion.source_file_id)
        .where(
            SourceFileVersion.ragflow_document_id.in_(document_ids),
            not_deleted(SourceFileVersion),
            not_deleted(SourceFile),
        )
    )
    mapping: dict[str, ActiveDocumentIdentity] = {}
    for version, source_file in result.all():
        if not version.ragflow_document_id:
            continue
        mapping[version.ragflow_document_id] = ActiveDocumentIdentity(
            source_file_id=source_file.id,
            file_version_id=version.id,
            knowledge_base_id=source_file.knowledge_base_id,
            org_id=source_file.org_id,
            active_version_id=source_file.active_version_id,
        )
    return mapping


async def _lookup_version_by_document(db: AsyncSession, document_id: str) -> SourceFileVersion | None:
    result = await db.execute(
        select(SourceFileVersion).where(
            SourceFileVersion.ragflow_document_id == document_id,
            not_deleted(SourceFileVersion),
        )
    )
    return result.scalar_one_or_none()

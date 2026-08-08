"""Chunk security cleaner."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.ragflow.client import RagflowClient
from app.integrations.ragflow.models import RagflowChunk
from app.models.source_file_version import SourceFileVersion

logger = logging.getLogger(__name__)


async def clean_chunks(
    db: AsyncSession,
    ragflow: RagflowClient,
    chunks: list[RagflowChunk],
    *,
    allowed_source_file_ids: set[str],
    dataset_id_by_document: dict[str, str] | None = None,
) -> tuple[list[RagflowChunk], int]:
    """Return (safe_chunks, filtered_count). Drops unauthorized or unidentifiable chunks."""
    safe: list[RagflowChunk] = []
    filtered = 0
    doc_meta_cache: dict[str, dict] = {}

    for chunk in chunks:
        source_file_id = None
        meta = chunk.document_metadata or {}
        source_file_id = meta.get("nk_source_file_id")

        if not source_file_id and chunk.document_id:
            if chunk.document_id in doc_meta_cache:
                source_file_id = doc_meta_cache[chunk.document_id].get("nk_source_file_id")
            else:
                version = await _lookup_version_by_document(db, chunk.document_id)
                if version:
                    source_file_id = version.source_file_id
                    doc_meta_cache[chunk.document_id] = {"nk_source_file_id": source_file_id}
                else:
                    dataset_id = chunk.dataset_id or chunk.kb_id
                    if dataset_id_by_document and chunk.document_id in dataset_id_by_document:
                        dataset_id = dataset_id_by_document[chunk.document_id]
                    if dataset_id:
                        try:
                            docs = await ragflow.list_documents(dataset_id, id=chunk.document_id, page_size=1)
                            if docs:
                                fields = docs[0].meta_fields or {}
                                doc_meta_cache[chunk.document_id] = fields
                                source_file_id = fields.get("nk_source_file_id")
                                chunk.document_metadata = {**meta, **fields}
                        except Exception:
                            logger.warning("failed to resolve metadata for document_id=%s", chunk.document_id)

        if not source_file_id:
            filtered += 1
            logger.warning("drop chunk without source identity chunk_id=%s", chunk.id)
            continue
        if source_file_id not in allowed_source_file_ids:
            filtered += 1
            continue
        if "nk_source_file_id" not in chunk.document_metadata:
            chunk.document_metadata = {**chunk.document_metadata, "nk_source_file_id": source_file_id}
        safe.append(chunk)

    return safe, filtered


async def _lookup_version_by_document(db: AsyncSession, document_id: str) -> SourceFileVersion | None:
    from sqlalchemy import select

    from app.models.base import not_deleted

    result = await db.execute(
        select(SourceFileVersion).where(
            SourceFileVersion.ragflow_document_id == document_id,
            not_deleted(SourceFileVersion),
        )
    )
    return result.scalar_one_or_none()

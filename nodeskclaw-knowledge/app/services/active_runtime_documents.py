"""ActiveRuntimeDocumentResolver — ACTIVE FileVersion → RAGFlow document mapping."""

# @lat: [[knowledge-objects#Build Job]]
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.base import not_deleted
from app.models.enums import SourceFileStatus
from app.models.source_file import SourceFile
from app.models.source_file_version import SourceFileVersion
from app.runtime.ragflow import RagflowRuntimeAdapter


@dataclass
class ActiveRuntimeDocument:
    source_file_id: str
    file_version_id: str
    ragflow_document_id: str


@dataclass
class ActiveDocumentResolution:
    documents: list[ActiveRuntimeDocument] = field(default_factory=list)
    blocked: list[dict[str, Any]] = field(default_factory=list)


async def resolve_active_documents(db: AsyncSession, knowledge_base_id: str) -> ActiveDocumentResolution:
    result = await db.execute(
        select(SourceFile, SourceFileVersion)
        .join(SourceFileVersion, SourceFileVersion.id == SourceFile.active_version_id)
        .where(
            SourceFile.knowledge_base_id == knowledge_base_id,
            SourceFile.status == SourceFileStatus.active.value,
            SourceFile.active_version_id.is_not(None),
            SourceFileVersion.ragflow_document_id.is_not(None),
            not_deleted(SourceFile),
            not_deleted(SourceFileVersion),
        )
    )
    documents: list[ActiveRuntimeDocument] = []
    for sf, version in result.all():
        if not version.ragflow_document_id:
            continue
        documents.append(
            ActiveRuntimeDocument(
                source_file_id=sf.id,
                file_version_id=version.id,
                ragflow_document_id=version.ragflow_document_id,
            )
        )
    return ActiveDocumentResolution(documents=documents)


async def validate_documents_active(
    adapter: RagflowRuntimeAdapter,
    dataset_id: str,
    documents: list[ActiveRuntimeDocument],
) -> ActiveDocumentResolution:
    valid: list[ActiveRuntimeDocument] = []
    blocked: list[dict[str, Any]] = []
    for doc in documents:
        remote_docs = await adapter.client.list_documents(dataset_id, id=doc.ragflow_document_id, page_size=1)
        if not remote_docs:
            blocked.append(
                {
                    "ragflow_document_id": doc.ragflow_document_id,
                    "file_version_id": doc.file_version_id,
                    "reason": "document_missing",
                }
            )
            continue
        remote = remote_docs[0]
        if remote.enabled is False:
            blocked.append(
                {
                    "ragflow_document_id": doc.ragflow_document_id,
                    "file_version_id": doc.file_version_id,
                    "reason": "document_disabled",
                }
            )
            continue
        meta = remote.meta_fields or {}
        remote_version_id = str(meta.get("nk_file_version_id") or "")
        if remote_version_id and remote_version_id != doc.file_version_id:
            blocked.append(
                {
                    "ragflow_document_id": doc.ragflow_document_id,
                    "file_version_id": doc.file_version_id,
                    "reason": "metadata_mismatch",
                    "expected_file_version_id": doc.file_version_id,
                    "observed_file_version_id": remote_version_id,
                }
            )
            continue
        valid.append(doc)
    return ActiveDocumentResolution(documents=valid, blocked=blocked)


async def resolve_and_validate_active_documents(
    db: AsyncSession,
    adapter: RagflowRuntimeAdapter,
    *,
    knowledge_base_id: str,
    dataset_id: str,
) -> ActiveDocumentResolution:
    resolved = await resolve_active_documents(db, knowledge_base_id)
    if not resolved.documents:
        return resolved
    return await validate_documents_active(adapter, dataset_id, resolved.documents)


def iter_document_batches(document_ids: list[str], batch_size: int | None = None) -> list[list[str]]:
    size = batch_size or settings.RAGFLOW_BUILD_BATCH_SIZE
    if size <= 0:
        size = 50
    return [document_ids[i : i + size] for i in range(0, len(document_ids), size)]

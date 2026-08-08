"""Reconciliation for RAGFlow drift, delete recovery and superseded documents."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.ragflow.client import RagflowClient
from app.integrations.ragflow.exceptions import RagflowError
from app.models.base import not_deleted
from app.models.enums import AuditAction, KnowledgeBaseStatus, SourceFileStatus
from app.models.knowledge_base import KnowledgeBase
from app.models.source_file import SourceFile
from app.models.source_file_version import SourceFileVersion
from app.services.audit_service import write_audit
from app.services.ingestion_service import build_meta_fields

logger = logging.getLogger(__name__)


async def _disable_superseded_enabled_documents(db: AsyncSession, ragflow: RagflowClient) -> int:
    result = await db.execute(
        select(SourceFileVersion, SourceFile, KnowledgeBase)
        .join(SourceFile, SourceFile.id == SourceFileVersion.source_file_id)
        .join(KnowledgeBase, KnowledgeBase.id == SourceFile.knowledge_base_id)
        .where(
            SourceFileVersion.parse_status == "superseded",
            SourceFileVersion.ragflow_document_id.is_not(None),
            not_deleted(SourceFileVersion),
            not_deleted(SourceFile),
            not_deleted(KnowledgeBase),
            KnowledgeBase.ragflow_dataset_id.is_not(None),
        )
    )
    disabled = 0
    for version, sf, kb in result.all():
        if not kb.ragflow_dataset_id or not version.ragflow_document_id:
            continue
        try:
            docs = await ragflow.list_documents(kb.ragflow_dataset_id, id=version.ragflow_document_id, page_size=1)
            if not docs:
                continue
            if docs[0].enabled is False:
                continue
            await ragflow.set_document_enabled(kb.ragflow_dataset_id, version.ragflow_document_id, False)
            disabled += 1
        except RagflowError as exc:
            logger.warning(
                "reconciliation disable superseded failed version=%s err=%s",
                version.id,
                exc.message_key,
            )
    return disabled


async def _retry_deleting_source_files(db: AsyncSession, ragflow: RagflowClient) -> int:
    result = await db.execute(
        select(SourceFile).where(
            SourceFile.status == SourceFileStatus.deleting.value,
            SourceFile.deleted_at.is_(None),
            not_deleted(SourceFile),
        )
    )
    completed = 0
    for sf in result.scalars().all():
        kb = await db.get(KnowledgeBase, sf.knowledge_base_id)
        if kb is None or not kb.ragflow_dataset_id:
            continue
        version_rows = await db.execute(
            select(SourceFileVersion).where(
                SourceFileVersion.source_file_id == sf.id,
                not_deleted(SourceFileVersion),
            )
        )
        versions = list(version_rows.scalars().all())
        doc_ids = [v.ragflow_document_id for v in versions if v.ragflow_document_id]
        try:
            if doc_ids:
                await ragflow.delete_documents(kb.ragflow_dataset_id, doc_ids)
            for version in versions:
                version.soft_delete()
            sf.soft_delete()
            completed += 1
        except RagflowError as exc:
            logger.warning("reconciliation delete source file failed id=%s err=%s", sf.id, exc.message_key)
    return completed


async def _retry_deleting_knowledge_bases(db: AsyncSession, ragflow: RagflowClient) -> int:
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.status == KnowledgeBaseStatus.deleting.value,
            KnowledgeBase.deleted_at.is_(None),
            not_deleted(KnowledgeBase),
        )
    )
    completed = 0
    for kb in result.scalars().all():
        if not kb.ragflow_dataset_id:
            kb.soft_delete()
            completed += 1
            continue
        try:
            await ragflow.delete_dataset(kb.ragflow_dataset_id)
            kb.soft_delete()
            completed += 1
        except RagflowError as exc:
            kb.last_error = exc.message
            logger.warning("reconciliation delete kb failed id=%s err=%s", kb.id, exc.message_key)
    return completed


async def _detect_metadata_drift(db: AsyncSession, ragflow: RagflowClient) -> int:
    result = await db.execute(
        select(SourceFileVersion, SourceFile, KnowledgeBase)
        .join(SourceFile, SourceFile.id == SourceFileVersion.source_file_id)
        .join(KnowledgeBase, KnowledgeBase.id == SourceFile.knowledge_base_id)
        .where(
            SourceFileVersion.ragflow_document_id.is_not(None),
            SourceFileVersion.parse_status.in_(["active", "parsing", "pending"]),
            not_deleted(SourceFileVersion),
            not_deleted(SourceFile),
            not_deleted(KnowledgeBase),
            KnowledgeBase.ragflow_dataset_id.is_not(None),
        )
        .limit(200)
    )
    drift_count = 0
    for version, sf, kb in result.all():
        if not kb.ragflow_dataset_id or not version.ragflow_document_id:
            continue
        try:
            docs = await ragflow.list_documents(kb.ragflow_dataset_id, id=version.ragflow_document_id, page_size=1)
        except RagflowError:
            continue
        if not docs:
            continue
        expected = build_meta_fields(
            source_file_id=sf.id,
            file_version_id=version.id,
            knowledge_base_id=kb.id,
            org_id=sf.org_id,
        )
        actual = docs[0].meta_fields or {}
        mismatch = any(str(actual.get(k, "")) != v for k, v in expected.items())
        if mismatch:
            drift_count += 1
            logger.warning(
                "metadata drift detected source_file=%s version=%s document=%s",
                sf.id,
                version.id,
                version.ragflow_document_id,
            )
            await write_audit(
                db,
                org_id=sf.org_id,
                member_id=None,
                action=AuditAction.metadata_mismatch.value,
                resource_type="source_file_version",
                resource_id=version.id,
                details={
                    "source_file_id": sf.id,
                    "ragflow_document_id": version.ragflow_document_id,
                    "expected": expected,
                    "actual": {k: actual.get(k) for k in expected},
                },
            )
    return drift_count


async def run_reconciliation(db: AsyncSession, ragflow: RagflowClient) -> dict[str, int]:
    disabled = await _disable_superseded_enabled_documents(db, ragflow)
    deleted_files = await _retry_deleting_source_files(db, ragflow)
    deleted_kbs = await _retry_deleting_knowledge_bases(db, ragflow)
    drift = await _detect_metadata_drift(db, ragflow)
    return {
        "superseded_disabled": disabled,
        "source_files_deleted": deleted_files,
        "knowledge_bases_deleted": deleted_kbs,
        "metadata_drift": drift,
    }

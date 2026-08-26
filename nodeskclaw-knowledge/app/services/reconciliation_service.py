"""Reconciliation for RAGFlow drift, delete recovery and superseded documents."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.ragflow.client import RagflowClient
from app.integrations.ragflow.exceptions import RagflowError
from app.models.base import not_deleted
from app.models.enums import AuditAction, KnowledgeBaseStatus, SourceFileStatus
from app.models.knowledge_base import KnowledgeBase
from app.models.reconciliation_run import ReconciliationRun
from app.models.source_file import SourceFile
from app.models.source_file_version import SourceFileVersion
from app.services.audit_service import write_audit
from app.services.metadata_service import build_meta_fields

logger = logging.getLogger(__name__)


async def _disable_superseded_enabled_documents(db: AsyncSession, ragflow: RagflowClient) -> tuple[int, int]:
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
    failed = 0
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
            failed += 1
            logger.warning(
                "reconciliation disable superseded failed version=%s err=%s",
                version.id,
                exc.message_key,
            )
    return disabled, failed


async def _retry_deleting_source_files(db: AsyncSession, ragflow: RagflowClient) -> tuple[int, int]:
    result = await db.execute(
        select(SourceFile).where(
            SourceFile.status == SourceFileStatus.deleting.value,
            SourceFile.deleted_at.is_(None),
            not_deleted(SourceFile),
        )
    )
    completed = 0
    failed = 0
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
            failed += 1
            logger.warning("reconciliation delete source file failed id=%s err=%s", sf.id, exc.message_key)
    return completed, failed


async def _retry_deleting_knowledge_bases(db: AsyncSession, ragflow: RagflowClient) -> tuple[int, int]:
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.status == KnowledgeBaseStatus.deleting.value,
            KnowledgeBase.deleted_at.is_(None),
            not_deleted(KnowledgeBase),
        )
    )
    completed = 0
    failed = 0
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
            failed += 1
            kb.last_error = exc.message
            logger.warning("reconciliation delete kb failed id=%s err=%s", kb.id, exc.message_key)
    return completed, failed


async def _repair_metadata_drift(db: AsyncSession, ragflow: RagflowClient) -> tuple[int, int, int, int]:
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
    checked_count = 0
    drift_count = 0
    repaired_count = 0
    failed_count = 0
    for version, sf, kb in result.all():
        if not kb.ragflow_dataset_id or not version.ragflow_document_id:
            continue
        checked_count += 1
        try:
            docs = await ragflow.list_documents(kb.ragflow_dataset_id, id=version.ragflow_document_id, page_size=1)
        except RagflowError:
            failed_count += 1
            continue
        if not docs:
            continue
        expected = build_meta_fields(
            source_file_id=sf.id,
            file_version_id=version.id,
            knowledge_base_id=kb.id,
            org_id=sf.org_id,
            metadata=sf.metadata_,
            metadata_revision=sf.metadata_revision,
        )
        actual = docs[0].meta_fields or {}
        mismatch = any(str(actual.get(k, "")) != v for k, v in expected.items())
        remote_revision = str(actual.get("nk_metadata_revision", ""))
        local_revision = str(int(sf.metadata_revision or 0))
        if remote_revision != local_revision:
            mismatch = True
        if not mismatch:
            continue
        drift_count += 1
        logger.warning(
            "metadata drift detected source_file=%s version=%s document=%s local_rev=%s remote_rev=%s",
            sf.id,
            version.id,
            version.ragflow_document_id,
            local_revision,
            remote_revision,
        )
        try:
            await ragflow.update_document_metadata(kb.ragflow_dataset_id, version.ragflow_document_id, expected)
            verify_docs = await ragflow.list_documents(
                kb.ragflow_dataset_id,
                id=version.ragflow_document_id,
                page_size=1,
            )
            verified = False
            if verify_docs:
                repaired_meta = verify_docs[0].meta_fields or {}
                verified = all(str(repaired_meta.get(k, "")) == v for k, v in expected.items())
            if verified:
                repaired_count += 1
                await write_audit(
                    db,
                    org_id=sf.org_id,
                    member_id=None,
                    action=AuditAction.metadata_repaired.value,
                    resource_type="source_file_version",
                    resource_id=version.id,
                    details={
                        "source_file_id": sf.id,
                        "ragflow_document_id": version.ragflow_document_id,
                        "strategy": "LOCAL_WINS",
                        "expected": expected,
                        "actual": {k: actual.get(k) for k in expected},
                        "status": "REPAIRED",
                    },
                )
            else:
                failed_count += 1
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
                        "strategy": "LOCAL_WINS",
                        "expected": expected,
                        "actual": {k: actual.get(k) for k in expected},
                        "status": "REPAIR_FAILED",
                    },
                )
        except RagflowError as exc:
            failed_count += 1
            logger.warning(
                "metadata repair failed source_file=%s version=%s err=%s",
                sf.id,
                version.id,
                exc.message_key,
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
                    "strategy": "LOCAL_WINS",
                    "expected": expected,
                    "actual": {k: actual.get(k) for k in expected},
                    "status": "REPAIR_FAILED",
                    "error": exc.message_key,
                },
            )
    return checked_count, drift_count, repaired_count, failed_count


async def _check_binding_drift(db: AsyncSession, ragflow: RagflowClient) -> tuple[int, int]:
    """Local Binding READY but Dataset missing → binding.error; do not auto-create Dataset."""
    from app.models.enums import RuntimeBindingStatus
    from app.models.runtime_binding import KnowledgeRuntimeBinding
    from app.services import metrics_service

    rows = await db.scalars(
        select(KnowledgeRuntimeBinding).where(
            KnowledgeRuntimeBinding.status == RuntimeBindingStatus.ready.value,
            not_deleted(KnowledgeRuntimeBinding),
        )
    )
    checked = 0
    drift = 0
    known_ids: set[str] | None = None
    try:
        datasets = await ragflow.list_datasets(page=1, page_size=100)
        known_ids = {d.id for d in datasets if getattr(d, "id", None)}
    except Exception:
        known_ids = None
    for binding in rows.all():
        checked += 1
        if known_ids is None:
            continue
        if binding.resource_id not in known_ids:
            binding.status = RuntimeBindingStatus.error.value
            binding.last_error = "dataset_missing"
            drift += 1
            metrics_service.observe_binding_drift(reason="dataset_missing")
    return checked, drift


async def _check_index_drift(db: AsyncSession) -> tuple[int, int]:
    from app.models.enums import IndexStateStatus
    from app.models.index_state import IndexState
    from app.services import metrics_service

    rows = await db.scalars(
        select(IndexState).where(
            IndexState.status == IndexStateStatus.ready.value,
            not_deleted(IndexState),
        )
    )
    checked = 0
    drift = 0
    for state in rows.all():
        checked += 1
        if state.status == IndexStateStatus.unsupported.value:
            continue
        # Watermark without build version indicates stale authority
        if state.source_watermark and int(state.build_version or 0) == 0:
            state.status = IndexStateStatus.stale.value
            drift += 1
            metrics_service.observe_index_drift(index_type=state.index_type)
    return checked, drift


async def _check_translation_drift(db: AsyncSession) -> tuple[int, int]:
    from app.models.translation import TranslationPage
    from app.services import metrics_service

    rows = await db.scalars(
        select(TranslationPage).where(
            TranslationPage.status == "completed",
            TranslationPage.artifact_uri.is_(None),
            not_deleted(TranslationPage),
        )
    )
    pages = list(rows.all())
    for page in pages:
        page.status = "partial"
        page.last_error = "artifact_missing"
        metrics_service.observe_translation_drift(reason="artifact_missing")
    return len(pages), len(pages)


# @lat: [[knowledge#Reconciliation Runs]]
async def run_reconciliation(db: AsyncSession, ragflow: RagflowClient) -> dict[str, int | str]:
    started_at = datetime.now(UTC)
    run = ReconciliationRun(
        id=str(uuid.uuid4()),
        started_at=started_at,
        status="running",
        checked_count=0,
        drifted_count=0,
        repaired_count=0,
        failed_count=0,
    )
    db.add(run)
    await db.flush()

    try:
        disabled, disabled_failed = await _disable_superseded_enabled_documents(db, ragflow)
        deleted_files, files_failed = await _retry_deleting_source_files(db, ragflow)
        deleted_kbs, kbs_failed = await _retry_deleting_knowledge_bases(db, ragflow)
        checked, drift, repaired, meta_failed = await _repair_metadata_drift(db, ragflow)
        binding_checked, binding_drift = await _check_binding_drift(db, ragflow)
        index_checked, index_drift = await _check_index_drift(db)
        translation_checked, translation_drift = await _check_translation_drift(db)

        repaired_total = disabled + deleted_files + deleted_kbs + repaired
        failed_total = disabled_failed + files_failed + kbs_failed + meta_failed
        run.checked_count = (
            checked
            + disabled
            + deleted_files
            + deleted_kbs
            + binding_checked
            + index_checked
            + translation_checked
        )
        run.drifted_count = drift + binding_drift + index_drift + translation_drift
        run.repaired_count = repaired_total
        run.failed_count = failed_total
        run.status = "success"
        run.finished_at = datetime.now(UTC)
        await db.commit()
        return {
            "superseded_disabled": disabled,
            "source_files_deleted": deleted_files,
            "knowledge_bases_deleted": deleted_kbs,
            "metadata_drift": drift,
            "metadata_repaired": repaired,
            "binding_drift": binding_drift,
            "index_drift": index_drift,
            "translation_drift": translation_drift,
            "checked": run.checked_count,
            "failed": failed_total,
            "reconciliation_run_id": run.id,
        }
    except Exception as exc:
        logger.exception(
            "reconciliation failed run_id=%s message_key=%s",
            run.id,
            "errors.knowledge.reconciliation_failed",
        )
        run.status = "failed"
        run.error_message = str(exc)[:2000]
        run.finished_at = datetime.now(UTC)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
        raise

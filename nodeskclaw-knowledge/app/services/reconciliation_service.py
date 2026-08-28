"""Reconciliation for RAGFlow drift, delete recovery and superseded documents."""

from __future__ import annotations

import copy
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.ragflow.exceptions import RagflowError
from app.runtime.ragflow import RagflowRuntimeAdapter
from app.models.base import not_deleted
from app.models.enums import AuditAction, BindingDriftStatus, KnowledgeBaseStatus, SourceFileStatus
from app.models.knowledge_base import KnowledgeBase
from app.models.reconciliation_run import ReconciliationRun
from app.models.source_file import SourceFile
from app.models.source_file_version import SourceFileVersion
from app.services import advisory_lock, runtime_binding_service
from app.services.audit_service import write_audit
from app.services.metadata_service import build_meta_fields

logger = logging.getLogger(__name__)


def normalize_runtime_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not raw:
        return {}
    parser_config = copy.deepcopy(raw.get("parser_config") or {})
    return {
        "embedding_model": raw.get("embedding_model"),
        "chunk_method": raw.get("chunk_method"),
        "parser_config": parser_config,
        "name": raw.get("name"),
        "description": raw.get("description"),
    }


def runtime_config_diff(desired: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
    diff: dict[str, Any] = {}
    for key in ("embedding_model", "chunk_method", "name", "description"):
        if desired.get(key) != observed.get(key):
            diff[key] = {"desired": desired.get(key), "observed": observed.get(key)}
    desired_parser = desired.get("parser_config") or {}
    observed_parser = observed.get("parser_config") or {}
    if desired_parser != observed_parser:
        diff["parser_config"] = {"desired": desired_parser, "observed": observed_parser}
    return diff


async def reconcile_binding_config(
    db: AsyncSession,
    knowledge_base_id: str,
    adapter,
    *,
    metadata_overrides: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    from app.runtime.ragflow import RagflowRuntimeAdapter

    if isinstance(adapter, RagflowRuntimeAdapter):
        adapter = RagflowRuntimeAdapter(client=adapter)
    elif not hasattr(adapter, "get_dataset_runtime_config"):
        adapter = RagflowRuntimeAdapter()

    await advisory_lock.kb_advisory_xact_lock(db, knowledge_base_id)
    kb = await db.get(KnowledgeBase, knowledge_base_id)
    if kb is None or kb.deleted_at is not None:
        return {"status": "skipped", "reason": "kb_missing"}

    binding = await runtime_binding_service.get_binding(db, knowledge_base_id)
    if binding is None:
        return {"status": "skipped", "reason": "binding_missing"}

    binding.drift_status = BindingDriftStatus.reconciling.value
    await db.flush()

    desired = await runtime_binding_service.compile_and_persist_desired_config(
        db,
        kb,
        binding,
        compat_profile=binding.capabilities,
    )
    if metadata_overrides:
        for key, value in metadata_overrides.items():
            if value is not None:
                desired[key] = value

    dataset_id = binding.resource_id
    observed_raw: dict[str, Any] | None = None
    try:
        observed_raw = await adapter.get_dataset_runtime_config(dataset_id)
    except Exception as exc:
        binding.drift_status = BindingDriftStatus.error.value
        binding.last_error = str(exc)[:2000]
        await db.flush()
        return {"status": "error", "reason": "read_observed_failed", "error": str(exc)}

    observed = normalize_runtime_config(observed_raw)
    diff = runtime_config_diff(desired, observed)
    applied = False
    if diff:
        try:
            if "parser_config" in diff or any(k in diff for k in ("embedding_model", "chunk_method")):
                await adapter.configure_index(
                    dataset_id,
                    parser_config=desired.get("parser_config") or {},
                )
            update_fields: dict[str, Any] = {}
            for field in ("name", "description", "embedding_model", "chunk_method"):
                if field in diff and desired.get(field) is not None:
                    update_fields[field] = desired[field]
            if update_fields:
                await adapter.client.update_dataset(dataset_id, **update_fields)
            applied = True
        except RagflowError as exc:
            binding.drift_status = BindingDriftStatus.error.value
            binding.last_error = exc.message
            await db.flush()
            return {"status": "error", "reason": "apply_failed", "diff": diff, "error": exc.message}

    read_back_raw = await adapter.get_dataset_runtime_config(dataset_id)
    read_back = normalize_runtime_config(read_back_raw)
    remaining = runtime_config_diff(desired, read_back)
    drift_status = BindingDriftStatus.in_sync.value if not remaining else BindingDriftStatus.drifted.value
    await runtime_binding_service.persist_observed_config(binding, read_back, drift_status=drift_status)
    binding.runtime_config = read_back
    binding.last_error = None if drift_status == BindingDriftStatus.in_sync.value else "config_drift"
    await db.flush()
    return {
        "status": "success",
        "applied": applied,
        "config_revision": binding.config_revision,
        "observed_revision": binding.observed_revision,
        "drift_status": drift_status,
        "diff": diff,
        "remaining_diff": remaining,
    }


async def _disable_superseded_enabled_documents(db: AsyncSession, ragflow: RagflowRuntimeAdapter) -> tuple[int, int]:
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
        )
    )
    disabled = 0
    failed = 0
    for version, sf, kb in result.all():
        dataset_id = await runtime_binding_service.get_dataset_id(db, kb)
        if not dataset_id or not version.ragflow_document_id:
            continue
        try:
            docs = await ragflow.list_documents(dataset_id, id=version.ragflow_document_id, page_size=1)
            if not docs:
                continue
            if docs[0].enabled is False:
                continue
            await ragflow.set_document_enabled(dataset_id, version.ragflow_document_id, False)
            disabled += 1
        except RagflowError as exc:
            failed += 1
            logger.warning(
                "reconciliation disable superseded failed version=%s err=%s",
                version.id,
                exc.message_key,
            )
    return disabled, failed


async def _retry_deleting_source_files(db: AsyncSession, ragflow: RagflowRuntimeAdapter) -> tuple[int, int]:
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
        dataset_id = await runtime_binding_service.get_dataset_id(db, kb) if kb else None
        if kb is None or not dataset_id:
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
                await ragflow.delete_documents(dataset_id, doc_ids)
            for version in versions:
                version.soft_delete()
            sf.soft_delete()
            completed += 1
        except RagflowError as exc:
            failed += 1
            logger.warning("reconciliation delete source file failed id=%s err=%s", sf.id, exc.message_key)
    return completed, failed


async def _retry_deleting_knowledge_bases(db: AsyncSession, ragflow: RagflowRuntimeAdapter) -> tuple[int, int]:
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
        dataset_id = await runtime_binding_service.get_dataset_id(db, kb)
        if not dataset_id:
            kb.soft_delete()
            completed += 1
            continue
        try:
            await ragflow.delete_dataset(dataset_id)
            kb.soft_delete()
            completed += 1
        except RagflowError as exc:
            failed += 1
            kb.last_error = exc.message
            logger.warning("reconciliation delete kb failed id=%s err=%s", kb.id, exc.message_key)
    return completed, failed


async def _repair_metadata_drift(db: AsyncSession, ragflow: RagflowRuntimeAdapter) -> tuple[int, int, int, int]:
    batch_size = 200
    cursor_updated_at: datetime | None = None
    cursor_id: str | None = None
    checked_count = 0
    drift_count = 0
    repaired_count = 0
    failed_count = 0
    while True:
        stmt = (
            select(SourceFileVersion, SourceFile, KnowledgeBase)
            .join(SourceFile, SourceFile.id == SourceFileVersion.source_file_id)
            .join(KnowledgeBase, KnowledgeBase.id == SourceFile.knowledge_base_id)
            .where(
                SourceFileVersion.ragflow_document_id.is_not(None),
                SourceFileVersion.parse_status.in_(["active", "parsing", "pending"]),
                not_deleted(SourceFileVersion),
                not_deleted(SourceFile),
                not_deleted(KnowledgeBase),
            )
            .order_by(SourceFileVersion.updated_at.asc(), SourceFileVersion.id.asc())
        )
        if cursor_updated_at is not None and cursor_id is not None:
            stmt = stmt.where(
                or_(
                    SourceFileVersion.updated_at > cursor_updated_at,
                    and_(
                        SourceFileVersion.updated_at == cursor_updated_at,
                        SourceFileVersion.id > cursor_id,
                    ),
                )
            )
        stmt = stmt.limit(batch_size)
        rows = (await db.execute(stmt)).all()
        if not rows:
            break
        for version, sf, kb in rows:
            dataset_id = await runtime_binding_service.get_dataset_id(db, kb)
            if not dataset_id or not version.ragflow_document_id:
                continue
            checked_count += 1
            try:
                docs = await ragflow.list_documents(dataset_id, id=version.ragflow_document_id, page_size=1)
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
                await ragflow.update_document_metadata(dataset_id, version.ragflow_document_id, expected)
                verify_docs = await ragflow.list_documents(
                    dataset_id,
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
        last_version = rows[-1][0]
        cursor_updated_at = last_version.updated_at
        cursor_id = last_version.id
        if len(rows) < batch_size:
            break
    return checked_count, drift_count, repaired_count, failed_count


async def _check_binding_drift(db: AsyncSession, ragflow: RagflowRuntimeAdapter) -> tuple[int, int]:
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
        known_ids = set()
        page = 1
        page_size = 100
        while True:
            datasets = await ragflow.list_datasets(page=page, page_size=page_size)
            if not datasets:
                break
            known_ids.update(d.id for d in datasets if getattr(d, "id", None))
            if len(datasets) < page_size:
                break
            page += 1
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


async def _reconcile_all_binding_configs(db: AsyncSession, adapter: RagflowRuntimeAdapter) -> int:
    from app.models.runtime_binding import KnowledgeRuntimeBinding

    rows = await db.scalars(
        select(KnowledgeRuntimeBinding).where(
            KnowledgeRuntimeBinding.deleted_at.is_(None),
            not_deleted(KnowledgeRuntimeBinding),
        )
    )
    reconciled = 0
    for binding in rows.all():
            if binding.drift_status in {
                BindingDriftStatus.drifted.value,
                BindingDriftStatus.unknown.value,
                BindingDriftStatus.error.value,
            }:
                result = await reconcile_binding_config(db, binding.knowledge_base_id, adapter)
                if result.get("status") == "success":
                    reconciled += 1
    return reconciled


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
async def run_reconciliation(db: AsyncSession, ragflow: RagflowRuntimeAdapter) -> dict[str, int | str]:
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
        config_reconciled = await _reconcile_all_binding_configs(db, ragflow)
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
            "binding_config_reconciled": config_reconciled,
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


def build_runtime_diagnostics(binding) -> dict[str, Any]:
    if binding is None:
        return {
            "binding_status": "missing",
            "runtime_version": None,
            "drift_status": None,
            "capabilities": {},
            "desired_revision": None,
            "observed_revision": None,
            "last_reconciled_at": None,
            "last_observed_at": None,
            "last_capability_probe_at": None,
        }
    return {
        "binding_status": binding.status,
        "runtime_version": binding.runtime_version,
        "drift_status": binding.drift_status,
        "capabilities": binding.capabilities or {},
        "desired_revision": binding.config_revision,
        "observed_revision": binding.observed_revision,
        "last_reconciled_at": binding.last_reconciled_at.isoformat() if binding.last_reconciled_at else None,
        "last_observed_at": binding.last_observed_at.isoformat() if binding.last_observed_at else None,
        "last_capability_probe_at": (
            binding.last_capability_probe_at.isoformat() if binding.last_capability_probe_at else None
        ),
        "last_capability_probe_error": binding.last_capability_probe_error,
        "last_error": binding.last_error,
    }


async def reconcile_knowledge_base_runtime(
    db: AsyncSession,
    adapter: RagflowRuntimeAdapter,
    knowledge_base_id: str,
    *,
    repair_mode: str | None = None,
) -> dict[str, Any]:
    from app.services import metrics_service

    kb = await db.get(KnowledgeBase, knowledge_base_id)
    if kb is None or kb.deleted_at is not None:
        metrics_service.observe_runtime_reconcile(status="error")
        return {"status": "error", "reason": "kb_missing"}

    binding = await runtime_binding_service.get_binding(db, knowledge_base_id)
    if binding is None:
        if repair_mode != "reprovision":
            metrics_service.observe_runtime_reconcile(status="skipped")
            return {"status": "skipped", "reason": "binding_missing", "repaired": False}
        result = await adapter.provision_binding(
            db,
            kb=kb,
            embedding_model=kb.embedding_model,
            chunk_method=kb.chunk_method,
            parser_config=kb.parser_config,
            description=kb.description,
            name=kb.name,
            org_id=kb.org_id,
        )
        binding = await runtime_binding_service.get_binding(db, knowledge_base_id)
        kb.ragflow_dataset_id = result.resource_id
        await db.flush()

    await runtime_binding_service.probe_and_persist_binding_capabilities(
        db,
        knowledge_base_id=knowledge_base_id,
        adapter=adapter,
    )
    reconcile_result = await reconcile_binding_config(db, knowledge_base_id, adapter)
    if binding is not None:
        binding.last_reconciled_at = datetime.now(UTC)
        await db.flush()
    status = str(reconcile_result.get("status") or "unknown")
    metrics_service.observe_runtime_reconcile(status=status)
    return {
        **reconcile_result,
        "repaired": bool(reconcile_result.get("applied")),
        "repair_mode": repair_mode,
    }

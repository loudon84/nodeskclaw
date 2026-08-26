"""Ingestion state machine: upload -> metadata -> parse dispatch -> worker poll -> activate."""

from __future__ import annotations

import hashlib
import logging
import tempfile
from datetime import UTC, datetime, timedelta
from typing import BinaryIO

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.integrations.ragflow.client import RagflowClient
from app.integrations.ragflow.exceptions import RagflowError
from app.models.base import not_deleted
from app.models.enums import IngestionJobStatus, KbPermission, SourceFileStatus
from app.models.ingestion_job import IngestionJob
from app.models.knowledge_base import KnowledgeBase
from app.models.source_file import SourceFile
from app.models.source_file_version import SourceFileVersion
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_base_service, runtime_binding_service, source_file_service
from app.services.metadata_service import build_meta_fields, validate_metadata_values
from app.services.permission_service import has_kb_permission
from app.services.source_file_service import activate_version, next_version_no, sha256_bytes

logger = logging.getLogger(__name__)

BACKOFF_SECONDS = [2, 4, 8, 16, 30]
LEASE_SECONDS = 30
UPLOAD_CHUNK_SIZE = 1024 * 1024
SPOOL_MAX_SIZE = 8 * 1024 * 1024


def _now() -> datetime:
    return datetime.now(UTC)


def _backoff_seconds(attempt_count: int) -> int:
    idx = min(max(attempt_count - 1, 0), len(BACKOFF_SECONDS) - 1)
    return BACKOFF_SECONDS[idx]


def _max_upload_bytes() -> int:
    return settings.KNOWLEDGE_UPLOAD_MAX_MB * 1024 * 1024


def _validate_upload_size(size: int) -> None:
    max_bytes = _max_upload_bytes()
    if size > max_bytes:
        raise BadRequestError(
            message=f"文件大小超过 {settings.KNOWLEDGE_UPLOAD_MAX_MB}MB 限制",
            message_key="errors.knowledge.upload_too_large",
            message_params={"max_mb": str(settings.KNOWLEDGE_UPLOAD_MAX_MB)},
        )


# @lat: [[knowledge#Ingestion Worker]]
async def read_upload_spooled(upload: UploadFile) -> tuple[tempfile.SpooledTemporaryFile, int, str]:
    max_bytes = _max_upload_bytes()
    spool = tempfile.SpooledTemporaryFile(max_size=SPOOL_MAX_SIZE)
    hasher = hashlib.sha256()
    total = 0
    try:
        while True:
            chunk = await upload.read(UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise BadRequestError(
                    message=f"文件大小超过 {settings.KNOWLEDGE_UPLOAD_MAX_MB}MB 限制",
                    message_key="errors.knowledge.upload_too_large",
                    message_params={"max_mb": str(settings.KNOWLEDGE_UPLOAD_MAX_MB)},
                )
            hasher.update(chunk)
            spool.write(chunk)
        spool.seek(0)
        return spool, total, hasher.hexdigest()
    except Exception:
        spool.close()
        raise


def _sync_document_runtime(version: SourceFileVersion, doc) -> None:
    version.ragflow_run = doc.run
    version.ragflow_status = doc.run
    version.ragflow_progress = doc.progress
    version.ragflow_progress_msg = doc.progress_msg
    version.chunk_count = doc.chunk_count
    version.token_count = doc.token_count
    version.process_duration = doc.process_duration


def _metadata_consistent(meta: dict, *, sf: SourceFile, version: SourceFileVersion, kb: KnowledgeBase) -> bool:
    expected = build_meta_fields(
        source_file_id=sf.id,
        file_version_id=version.id,
        knowledge_base_id=kb.id,
        org_id=sf.org_id,
        metadata=sf.metadata_,
        metadata_revision=sf.metadata_revision,
    )
    for key, value in expected.items():
        if str(meta.get(key, "")) != value:
            return False
    return True


async def ingest_upload(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowClient,
    *,
    knowledge_base_id: str,
    file_name: str,
    mime_type: str | None,
    content: bytes | None = None,
    file_obj: BinaryIO | None = None,
    file_size: int | None = None,
    sha256: str | None = None,
    source_file_id: str | None = None,
    metadata: dict | None = None,
) -> tuple[SourceFile, SourceFileVersion, IngestionJob]:
    from app.services.ingestion_facade import ingest_from_member

    return await ingest_from_member(
        db,
        member,
        ragflow,
        knowledge_base_id=knowledge_base_id,
        file_name=file_name,
        mime_type=mime_type,
        content=content,
        file_obj=file_obj,
        file_size=file_size,
        sha256=sha256,
        source_file_id=source_file_id,
        metadata=metadata,
    )

async def reparse_source_file(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowClient,
    source_file_id: str,
) -> IngestionJob:
    sf = await source_file_service.get_source_file(db, member, source_file_id)
    if not await has_kb_permission(db, member, sf.knowledge_base_id, KbPermission.upload.value):
        raise ForbiddenError()
    version = await db.get(SourceFileVersion, sf.active_version_id) if sf.active_version_id else None
    if version is None or not version.ragflow_document_id:
        raise NotFoundError(message="没有可重新解析的版本", message_key="errors.knowledge.version_not_found")
    kb = await knowledge_base_service.get_knowledge_base(db, member, sf.knowledge_base_id)
    dataset_id = await runtime_binding_service.require_dataset_id(db, kb)

    job = IngestionJob(
        source_file_id=sf.id,
        file_version_id=version.id,
        ragflow_document_id=version.ragflow_document_id,
        status=IngestionJobStatus.metadata_synced.value,
        created_by_member_id=member.member_id,
    )
    db.add(job)
    await db.flush()
    try:
        meta = build_meta_fields(
            source_file_id=sf.id,
            file_version_id=version.id,
            knowledge_base_id=kb.id,
            org_id=member.org_id,
            metadata=sf.metadata_,
            metadata_revision=sf.metadata_revision,
        )
        await ragflow.update_document_metadata(dataset_id, version.ragflow_document_id, meta)
        await ragflow.parse_documents(dataset_id, [version.ragflow_document_id])
        version.parse_status = "parsing"
        version.ragflow_status = "UNSTART"
        job.status = IngestionJobStatus.parse_dispatched.value
        job.progress = 70
        job.next_run_at = _now()
        await db.commit()
        await db.refresh(job)
        return job
    except RagflowError as exc:
        job.status = IngestionJobStatus.failed.value
        job.error_code = exc.message_key
        job.error_message = exc.message
        job.finished_at = _now()
        await db.commit()
        raise BadRequestError(message=exc.message, message_key=exc.message_key) from exc


async def list_jobs(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    status: str | None = None,
    knowledge_base_id: str | None = None,
    source_file_id: str | None = None,
    created_by: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[IngestionJob], int]:
    filters = [IngestionJob.deleted_at.is_(None)]
    if status:
        filters.append(IngestionJob.status == status)
    if source_file_id:
        filters.append(IngestionJob.source_file_id == source_file_id)
    if created_by:
        filters.append(IngestionJob.created_by_member_id == created_by)

    base = select(IngestionJob)
    if knowledge_base_id:
        base = base.join(SourceFile, SourceFile.id == IngestionJob.source_file_id).where(
            SourceFile.knowledge_base_id == knowledge_base_id,
            SourceFile.org_id == member.org_id,
            not_deleted(SourceFile),
        )
    else:
        base = base.join(SourceFile, SourceFile.id == IngestionJob.source_file_id).where(
            SourceFile.org_id == member.org_id,
            not_deleted(SourceFile),
        )
    base = base.where(*filters)

    result = await db.execute(base.order_by(IngestionJob.created_at.desc()))
    jobs = list(result.scalars().all())
    visible: list[IngestionJob] = []
    for job in jobs:
        if job.created_by_member_id == member.member_id or member.is_super_admin:
            visible.append(job)
            continue
        sf = await db.get(SourceFile, job.source_file_id)
        if sf and sf.org_id == member.org_id and await has_kb_permission(
            db, member, sf.knowledge_base_id, KbPermission.read.value
        ):
            visible.append(job)
    total = len(visible)
    start = (page - 1) * page_size
    return visible[start : start + page_size], total


async def get_job(db: AsyncSession, member: KnowledgePrincipal, job_id: str) -> IngestionJob:
    job = await db.get(IngestionJob, job_id)
    if job is None or job.deleted_at is not None:
        raise NotFoundError(message="入库任务不存在", message_key="errors.knowledge.ingestion_job_not_found")
    if job.created_by_member_id != member.member_id and not member.is_super_admin:
        sf = await db.get(SourceFile, job.source_file_id)
        if sf is None or sf.org_id != member.org_id:
            raise NotFoundError(message="入库任务不存在", message_key="errors.knowledge.ingestion_job_not_found")
        if not await has_kb_permission(db, member, sf.knowledge_base_id, KbPermission.read.value):
            raise ForbiddenError()
    return job


async def retry_job(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowClient,
    job_id: str,
) -> IngestionJob:
    job = await get_job(db, member, job_id)
    if job.status not in {IngestionJobStatus.failed.value, IngestionJobStatus.cancelled.value}:
        raise BadRequestError(message="当前状态不可重试", message_key="errors.knowledge.job_retry_not_allowed")

    sf = await db.get(SourceFile, job.source_file_id)
    version = await db.get(SourceFileVersion, job.file_version_id)
    if sf is None or version is None or not version.ragflow_document_id:
        raise NotFoundError(message="版本不存在", message_key="errors.knowledge.version_not_found")
    kb = await knowledge_base_service.get_knowledge_base(db, member, sf.knowledge_base_id)
    dataset_id = await runtime_binding_service.require_dataset_id(db, kb)
    if not await has_kb_permission(db, member, kb.id, KbPermission.upload.value):
        raise ForbiddenError()

    job.status = IngestionJobStatus.metadata_synced.value
    job.error_code = None
    job.error_message = None
    job.finished_at = None
    job.attempt_count = 0
    job.next_run_at = None
    job.lease_owner = None
    job.lease_token = None
    job.lease_until = None
    job.last_heartbeat_at = None

    meta = build_meta_fields(
        source_file_id=sf.id,
        file_version_id=version.id,
        knowledge_base_id=kb.id,
        org_id=sf.org_id,
        metadata=sf.metadata_,
        metadata_revision=sf.metadata_revision,
    )
    await ragflow.update_document_metadata(dataset_id, version.ragflow_document_id, meta)
    await ragflow.parse_documents(dataset_id, [version.ragflow_document_id])
    version.parse_status = "parsing"
    version.ragflow_status = "UNSTART"
    job.status = IngestionJobStatus.parse_dispatched.value
    job.progress = 70
    job.next_run_at = _now()
    await db.commit()
    await db.refresh(job)
    return job


async def cancel_job(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowClient,
    job_id: str,
) -> IngestionJob:
    job = await get_job(db, member, job_id)
    if job.status in {
        IngestionJobStatus.active.value,
        IngestionJobStatus.failed.value,
        IngestionJobStatus.cancelled.value,
    }:
        raise BadRequestError(message="当前状态不可取消", message_key="errors.knowledge.job_cancel_not_allowed")

    sf = await db.get(SourceFile, job.source_file_id)
    version = await db.get(SourceFileVersion, job.file_version_id)
    kb = await db.get(KnowledgeBase, sf.knowledge_base_id) if sf else None
    dataset_id = await runtime_binding_service.get_dataset_id(db, kb) if kb else None
    if kb and dataset_id and job.ragflow_document_id:
        try:
            await ragflow.stop_parsing(dataset_id, [job.ragflow_document_id])
        except RagflowError:
            logger.warning("stop_parsing failed job_id=%s", job.id)

    job.status = IngestionJobStatus.cancelled.value
    job.finished_at = _now()
    job.lease_owner = None
    job.lease_token = None
    job.lease_until = None
    job.last_heartbeat_at = None
    if version:
        version.parse_status = "failed"
        version.ragflow_status = "CANCEL"
    if sf and sf.active_version_id != job.file_version_id:
        sf.status = SourceFileStatus.active.value if sf.active_version_id else SourceFileStatus.error.value
    await db.commit()
    await db.refresh(job)
    return job


async def claim_next_job(db: AsyncSession, *, lease_owner: str) -> tuple[IngestionJob, str] | None:
    from app.workers.job_leasing import claim_next

    statuses = [
        IngestionJobStatus.parse_dispatched.value,
        IngestionJobStatus.parsing.value,
        IngestionJobStatus.validating.value,
    ]
    claimed = await claim_next(
        db,
        IngestionJob,
        statuses=statuses,
        lease_owner=lease_owner,
        lease_seconds=LEASE_SECONDS,
        order_by=(IngestionJob.next_run_at.asc().nullsfirst(), IngestionJob.created_at.asc()),
        commit=True,
    )
    if claimed is None:
        return None
    job, lease_token = claimed
    job.last_polled_at = _now()
    await db.commit()
    await db.refresh(job)
    return job, lease_token


# @lat: [[knowledge#Ingestion Worker]]
async def process_leased_job(
    db: AsyncSession,
    ragflow: RagflowClient,
    job: IngestionJob,
    *,
    lease_owner: str | None = None,
    lease_token: str | None = None,
) -> bool:
    from app.workers.job_leasing import ownership_matches

    if lease_owner and lease_token and not ownership_matches(job, lease_owner=lease_owner, lease_token=lease_token):
        await db.rollback()
        return False

    sf = await db.get(SourceFile, job.source_file_id)
    version = await db.get(SourceFileVersion, job.file_version_id)
    if sf is None or version is None or not version.ragflow_document_id:
        job.status = IngestionJobStatus.failed.value
        job.error_message = "missing source file or version"
        job.finished_at = _now()
        return True

    kb = await db.get(KnowledgeBase, sf.knowledge_base_id)
    dataset_id = await runtime_binding_service.get_dataset_id(db, kb) if kb else None
    if kb is None or not dataset_id:
        job.status = IngestionJobStatus.failed.value
        job.error_message = "knowledge base not ready"
        job.finished_at = _now()
        return True

    try:
        docs = await ragflow.list_documents(dataset_id, id=version.ragflow_document_id, page_size=1)
    except RagflowError as exc:
        job.attempt_count += 1
        if job.attempt_count >= job.max_attempts:
            job.status = IngestionJobStatus.failed.value
            job.error_code = exc.message_key
            job.error_message = exc.message
            job.finished_at = _now()
        else:
            job.next_run_at = _now() + timedelta(seconds=_backoff_seconds(job.attempt_count))
        return True
    except Exception as exc:
        job.attempt_count += 1
        if job.attempt_count >= job.max_attempts:
            job.status = IngestionJobStatus.failed.value
            job.error_message = str(exc)
            job.finished_at = _now()
        else:
            job.next_run_at = _now() + timedelta(seconds=_backoff_seconds(job.attempt_count))
        return True

    if not docs:
        job.attempt_count += 1
        if job.attempt_count >= job.max_attempts:
            job.status = IngestionJobStatus.failed.value
            job.error_message = "document not found in RAGFlow"
            job.finished_at = _now()
        else:
            job.next_run_at = _now() + timedelta(seconds=_backoff_seconds(job.attempt_count))
        return True

    doc = docs[0]
    _sync_document_runtime(version, doc)
    run = (doc.run or "UNSTART").upper()

    if run == "UNSTART":
        job.status = IngestionJobStatus.parse_dispatched.value
        job.progress = max(job.progress, 70)
        version.parse_status = "parsing"
        job.next_run_at = _now() + timedelta(seconds=2)
        return True

    if run == "RUNNING":
        job.status = IngestionJobStatus.parsing.value
        job.progress = max(job.progress, 80)
        version.parse_status = "parsing"
        job.next_run_at = _now() + timedelta(seconds=2)
        return True

    if run == "CANCEL":
        job.status = IngestionJobStatus.cancelled.value
        job.finished_at = _now()
        version.parse_status = "failed"
        version.ragflow_status = "CANCEL"
        if sf.active_version_id != version.id:
            sf.status = SourceFileStatus.active.value if sf.active_version_id else SourceFileStatus.error.value
        return True

    if run == "FAIL":
        job.status = IngestionJobStatus.failed.value
        job.error_message = doc.progress_msg or "RAGFlow parse failed"
        job.finished_at = _now()
        version.parse_status = "failed"
        version.ragflow_status = "FAIL"
        if sf.active_version_id != version.id:
            sf.status = SourceFileStatus.error.value if not sf.active_version_id else SourceFileStatus.active.value
        return True

    if run != "DONE":
        job.next_run_at = _now() + timedelta(seconds=2)
        return True

    job.status = IngestionJobStatus.validating.value
    job.progress = max(job.progress, 90)
    version.parse_status = "parsing"

    if not doc.chunk_count or doc.chunk_count <= 0:
        job.status = IngestionJobStatus.failed.value
        job.error_message = "parse completed with zero chunks"
        job.finished_at = _now()
        version.parse_status = "failed"
        if sf.active_version_id != version.id:
            sf.status = SourceFileStatus.error.value if not sf.active_version_id else SourceFileStatus.active.value
        return True

    meta = doc.meta_fields or {}
    if not _metadata_consistent(meta, sf=sf, version=version, kb=kb):
        job.status = IngestionJobStatus.failed.value
        job.error_message = "metadata mismatch"
        job.error_code = "errors.knowledge.metadata_mismatch"
        job.finished_at = _now()
        version.parse_status = "failed"
        if sf.active_version_id != version.id:
            sf.status = SourceFileStatus.error.value if not sf.active_version_id else SourceFileStatus.active.value
        return True

    old_version = None
    if sf.active_version_id and sf.active_version_id != version.id:
        old_version = await db.get(SourceFileVersion, sf.active_version_id)

    activate_version(sf, version, old_version)
    job.status = IngestionJobStatus.active.value
    job.progress = 100
    job.finished_at = _now()
    job.next_run_at = None

    if old_version and old_version.ragflow_document_id:
        try:
            await ragflow.set_document_enabled(dataset_id, old_version.ragflow_document_id, False)
        except Exception:
            logger.warning(
                "failed to disable old document dataset=%s document=%s",
                dataset_id,
                old_version.ragflow_document_id,
            )
    return True


async def finalize_leased_job(
    db: AsyncSession,
    job: IngestionJob,
    *,
    lease_owner: str,
    lease_token: str,
    clear_lease: bool = True,
) -> bool:
    """Commit job mutations only when the worker still owns the lease token."""
    from sqlalchemy import text as sql_text

    result = await db.execute(
        sql_text(
            """
            UPDATE knowledge_ingestion_jobs
            SET last_heartbeat_at = NOW()
            WHERE id = :id
              AND lease_owner = :owner
              AND lease_token = :token
              AND deleted_at IS NULL
            """
        ),
        {"id": job.id, "owner": lease_owner, "token": lease_token},
    )
    if result.rowcount == 0:
        await db.rollback()
        return False
    if clear_lease and job.status in {
        IngestionJobStatus.active.value,
        IngestionJobStatus.failed.value,
        IngestionJobStatus.cancelled.value,
    }:
        job.lease_owner = None
        job.lease_token = None
        job.lease_until = None
    await db.commit()
    return True

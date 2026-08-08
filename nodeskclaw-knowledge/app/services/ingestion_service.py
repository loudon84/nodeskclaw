"""Ingestion state machine: upload -> metadata -> parse dispatch -> worker poll -> activate."""

from __future__ import annotations

import hashlib
import logging
import tempfile
from datetime import UTC, datetime, timedelta
from typing import BinaryIO

from fastapi import UploadFile
from sqlalchemy import func, select
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
from app.services import knowledge_base_service, source_file_service
from app.services.permission_service import has_kb_permission
from app.services.source_file_service import activate_version, next_version_no, sha256_bytes

logger = logging.getLogger(__name__)

BACKOFF_SECONDS = [2, 4, 8, 16, 30]
LEASE_SECONDS = 30
UPLOAD_CHUNK_SIZE = 1024 * 1024
SPOOL_MAX_SIZE = 8 * 1024 * 1024


def build_meta_fields(
    *,
    source_file_id: str,
    file_version_id: str,
    knowledge_base_id: str,
    org_id: str,
) -> dict[str, str]:
    return {
        "nk_source_file_id": source_file_id,
        "nk_file_version_id": file_version_id,
        "nk_knowledge_base_id": knowledge_base_id,
        "nk_org_id": org_id,
    }


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
) -> tuple[SourceFile, SourceFileVersion, IngestionJob]:
    if file_obj is not None:
        size = int(file_size or 0)
        digest = sha256 or ""
        if not digest:
            raise BadRequestError(message="缺少文件摘要", message_key="errors.knowledge.upload_invalid")
    else:
        payload = content or b""
        _validate_upload_size(len(payload))
        size = len(payload)
        digest = sha256_bytes(payload)
        file_obj = None

    kb = await knowledge_base_service.get_knowledge_base(db, member, knowledge_base_id)
    if not kb.ragflow_dataset_id or kb.status != "active":
        raise BadRequestError(message="知识库未就绪", message_key="errors.knowledge.kb_not_ready")
    if not await has_kb_permission(db, member, kb.id, KbPermission.upload.value) and not await has_kb_permission(
        db, member, kb.id, KbPermission.manage.value
    ):
        raise ForbiddenError()

    if source_file_id:
        sf = await source_file_service.get_source_file(db, member, source_file_id)
        if sf.knowledge_base_id != knowledge_base_id:
            raise BadRequestError(message="源文件不属于该知识库", message_key="errors.knowledge.source_file_mismatch")
        old_version = await db.get(SourceFileVersion, sf.active_version_id) if sf.active_version_id else None
        sf.status = SourceFileStatus.updating.value
    else:
        existing = await db.execute(
            select(SourceFile).where(
                SourceFile.knowledge_base_id == knowledge_base_id,
                SourceFile.file_name == file_name,
                not_deleted(SourceFile),
            )
        )
        if existing.scalar_one_or_none():
            raise BadRequestError(message="同名文件已存在，请走版本更新", message_key="errors.knowledge.file_exists")
        sf = SourceFile(
            org_id=member.org_id,
            knowledge_base_id=knowledge_base_id,
            file_name=file_name,
            mime_type=mime_type,
            owner_member_id=member.member_id,
            status=SourceFileStatus.pending.value,
        )
        db.add(sf)
        await db.flush()
        old_version = None

    version = SourceFileVersion(
        source_file_id=sf.id,
        version_no=await next_version_no(db, sf.id),
        file_size=size,
        sha256=digest,
        uploaded_by_member_id=member.member_id,
        parse_status="pending",
        ragflow_status="UNSTART",
    )
    db.add(version)
    await db.flush()

    job = IngestionJob(
        source_file_id=sf.id,
        file_version_id=version.id,
        status=IngestionJobStatus.pending.value,
        created_by_member_id=member.member_id,
    )
    db.add(job)
    await db.flush()

    try:
        job.status = IngestionJobStatus.uploading.value
        job.progress = 10
        await db.flush()

        if file_obj is not None:
            document_id = await ragflow.upload_document(
                kb.ragflow_dataset_id,
                filename=file_name,
                mime=mime_type,
                file_obj=file_obj,
            )
        else:
            document_id = await ragflow.upload_document(
                kb.ragflow_dataset_id,
                content or b"",
                file_name,
                mime_type,
            )
        version.ragflow_document_id = document_id
        job.ragflow_document_id = document_id
        job.status = IngestionJobStatus.ragflow_uploaded.value
        job.progress = 40
        await db.flush()

        meta = build_meta_fields(
            source_file_id=sf.id,
            file_version_id=version.id,
            knowledge_base_id=kb.id,
            org_id=member.org_id,
        )
        await ragflow.update_document_metadata(kb.ragflow_dataset_id, document_id, meta)
        job.status = IngestionJobStatus.metadata_synced.value
        job.progress = 60
        await db.flush()

        await ragflow.parse_documents(kb.ragflow_dataset_id, [document_id])
        version.parse_status = "parsing"
        version.ragflow_status = "UNSTART"
        job.status = IngestionJobStatus.parse_dispatched.value
        job.progress = 70
        job.next_run_at = _now()
        await db.commit()
        await db.refresh(sf)
        await db.refresh(version)
        await db.refresh(job)
        return sf, version, job
    except RagflowError as exc:
        job.status = IngestionJobStatus.failed.value
        job.error_code = exc.message_key
        job.error_message = exc.message
        job.finished_at = _now()
        version.parse_status = "failed"
        if old_version is None:
            sf.status = SourceFileStatus.error.value
        else:
            sf.status = SourceFileStatus.active.value
        await db.commit()
        raise BadRequestError(message=exc.message, message_key=exc.message_key) from exc


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
    if not kb.ragflow_dataset_id:
        raise BadRequestError(message="知识库未就绪", message_key="errors.knowledge.kb_not_ready")

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
        )
        await ragflow.update_document_metadata(kb.ragflow_dataset_id, version.ragflow_document_id, meta)
        await ragflow.parse_documents(kb.ragflow_dataset_id, [version.ragflow_document_id])
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
    base = base.where(*filters)

    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0
    result = await db.execute(
        base.order_by(IngestionJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
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
    return visible, int(total)


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
    if not kb.ragflow_dataset_id:
        raise BadRequestError(message="知识库未就绪", message_key="errors.knowledge.kb_not_ready")
    if not await has_kb_permission(db, member, kb.id, KbPermission.upload.value):
        raise ForbiddenError()

    job.status = IngestionJobStatus.metadata_synced.value
    job.error_code = None
    job.error_message = None
    job.finished_at = None
    job.attempt_count = 0
    job.next_run_at = None
    job.lease_owner = None
    job.lease_until = None

    meta = build_meta_fields(
        source_file_id=sf.id,
        file_version_id=version.id,
        knowledge_base_id=kb.id,
        org_id=sf.org_id,
    )
    await ragflow.update_document_metadata(kb.ragflow_dataset_id, version.ragflow_document_id, meta)
    await ragflow.parse_documents(kb.ragflow_dataset_id, [version.ragflow_document_id])
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
    if kb and kb.ragflow_dataset_id and job.ragflow_document_id:
        try:
            await ragflow.stop_parsing(kb.ragflow_dataset_id, [job.ragflow_document_id])
        except RagflowError:
            logger.warning("stop_parsing failed job_id=%s", job.id)

    job.status = IngestionJobStatus.cancelled.value
    job.finished_at = _now()
    job.lease_owner = None
    job.lease_until = None
    if version:
        version.parse_status = "failed"
        version.ragflow_status = "CANCEL"
    if sf and sf.active_version_id != job.file_version_id:
        sf.status = SourceFileStatus.active.value if sf.active_version_id else SourceFileStatus.error.value
    await db.commit()
    await db.refresh(job)
    return job


async def claim_next_job(db: AsyncSession, *, lease_owner: str) -> IngestionJob | None:
    now = _now()
    statuses = [
        IngestionJobStatus.parse_dispatched.value,
        IngestionJobStatus.parsing.value,
        IngestionJobStatus.validating.value,
    ]
    result = await db.execute(
        select(IngestionJob)
        .where(
            IngestionJob.status.in_(statuses),
            IngestionJob.deleted_at.is_(None),
            (IngestionJob.next_run_at.is_(None)) | (IngestionJob.next_run_at <= now),
            (IngestionJob.lease_until.is_(None)) | (IngestionJob.lease_until < now),
        )
        .order_by(IngestionJob.next_run_at.asc().nullsfirst(), IngestionJob.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if job is None:
        return None
    job.lease_owner = lease_owner
    job.lease_until = now + timedelta(seconds=LEASE_SECONDS)
    job.last_polled_at = now
    await db.flush()
    return job


# @lat: [[knowledge#Ingestion Worker]]
async def process_leased_job(
    db: AsyncSession,
    ragflow: RagflowClient,
    job: IngestionJob,
) -> None:
    sf = await db.get(SourceFile, job.source_file_id)
    version = await db.get(SourceFileVersion, job.file_version_id)
    if sf is None or version is None or not version.ragflow_document_id:
        job.status = IngestionJobStatus.failed.value
        job.error_message = "missing source file or version"
        job.finished_at = _now()
        return

    kb = await db.get(KnowledgeBase, sf.knowledge_base_id)
    if kb is None or not kb.ragflow_dataset_id:
        job.status = IngestionJobStatus.failed.value
        job.error_message = "knowledge base not ready"
        job.finished_at = _now()
        return

    try:
        docs = await ragflow.list_documents(kb.ragflow_dataset_id, id=version.ragflow_document_id, page_size=1)
    except RagflowError as exc:
        job.attempt_count += 1
        if job.attempt_count >= job.max_attempts:
            job.status = IngestionJobStatus.failed.value
            job.error_code = exc.message_key
            job.error_message = exc.message
            job.finished_at = _now()
        else:
            job.next_run_at = _now() + timedelta(seconds=_backoff_seconds(job.attempt_count))
        return
    except Exception as exc:
        job.attempt_count += 1
        if job.attempt_count >= job.max_attempts:
            job.status = IngestionJobStatus.failed.value
            job.error_message = str(exc)
            job.finished_at = _now()
        else:
            job.next_run_at = _now() + timedelta(seconds=_backoff_seconds(job.attempt_count))
        return

    if not docs:
        job.attempt_count += 1
        if job.attempt_count >= job.max_attempts:
            job.status = IngestionJobStatus.failed.value
            job.error_message = "document not found in RAGFlow"
            job.finished_at = _now()
        else:
            job.next_run_at = _now() + timedelta(seconds=_backoff_seconds(job.attempt_count))
        return

    doc = docs[0]
    _sync_document_runtime(version, doc)
    run = (doc.run or "UNSTART").upper()

    if run == "UNSTART":
        job.status = IngestionJobStatus.parse_dispatched.value
        job.progress = max(job.progress, 70)
        version.parse_status = "parsing"
        job.next_run_at = _now() + timedelta(seconds=2)
        return

    if run == "RUNNING":
        job.status = IngestionJobStatus.parsing.value
        job.progress = max(job.progress, 80)
        version.parse_status = "parsing"
        job.next_run_at = _now() + timedelta(seconds=2)
        return

    if run == "CANCEL":
        job.status = IngestionJobStatus.cancelled.value
        job.finished_at = _now()
        version.parse_status = "failed"
        version.ragflow_status = "CANCEL"
        if sf.active_version_id != version.id:
            sf.status = SourceFileStatus.active.value if sf.active_version_id else SourceFileStatus.error.value
        return

    if run == "FAIL":
        job.status = IngestionJobStatus.failed.value
        job.error_message = doc.progress_msg or "RAGFlow parse failed"
        job.finished_at = _now()
        version.parse_status = "failed"
        version.ragflow_status = "FAIL"
        if sf.active_version_id != version.id:
            sf.status = SourceFileStatus.error.value if not sf.active_version_id else SourceFileStatus.active.value
        return

    if run != "DONE":
        job.next_run_at = _now() + timedelta(seconds=2)
        return

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
        return

    meta = doc.meta_fields or {}
    if not _metadata_consistent(meta, sf=sf, version=version, kb=kb):
        job.status = IngestionJobStatus.failed.value
        job.error_message = "metadata mismatch"
        job.error_code = "errors.knowledge.metadata_mismatch"
        job.finished_at = _now()
        version.parse_status = "failed"
        if sf.active_version_id != version.id:
            sf.status = SourceFileStatus.error.value if not sf.active_version_id else SourceFileStatus.active.value
        return

    old_version = None
    if sf.active_version_id and sf.active_version_id != version.id:
        old_version = await db.get(SourceFileVersion, sf.active_version_id)

    activate_version(sf, version, old_version)
    job.status = IngestionJobStatus.active.value
    job.progress = 100
    job.finished_at = _now()
    job.next_run_at = None
    job.lease_owner = None
    job.lease_until = None

    if old_version and old_version.ragflow_document_id:
        try:
            await ragflow.set_document_enabled(kb.ragflow_dataset_id, old_version.ragflow_document_id, False)
        except Exception:
            logger.warning(
                "failed to disable old document dataset=%s document=%s",
                kb.ragflow_dataset_id,
                old_version.ragflow_document_id,
            )

"""Ingestion state machine: upload -> metadata -> parse -> activate."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.integrations.ragflow.client import RagflowClient
from app.integrations.ragflow.exceptions import RagflowError
from app.models.base import not_deleted
from app.models.enums import IngestionJobStatus, KbPermission, SourceFileStatus
from app.models.ingestion_job import IngestionJob
from app.models.source_file import SourceFile
from app.models.source_file_version import SourceFileVersion
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_base_service, source_file_service
from app.services.permission_service import has_kb_permission
from app.services.source_file_service import activate_version, next_version_no, sha256_bytes

logger = logging.getLogger(__name__)


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


async def ingest_upload(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowClient,
    *,
    knowledge_base_id: str,
    file_name: str,
    content: bytes,
    mime_type: str | None,
    source_file_id: str | None = None,
) -> tuple[SourceFile, SourceFileVersion, IngestionJob]:
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
        file_size=len(content),
        sha256=sha256_bytes(content),
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

        document_id = await ragflow.upload_document(
            kb.ragflow_dataset_id,
            content,
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
        job.status = IngestionJobStatus.parsing.value
        version.parse_status = "parsing"
        version.ragflow_status = "RUNNING"
        job.progress = 80
        await db.flush()

        job.status = IngestionJobStatus.validating.value
        activate_version(sf, version, old_version)
        job.status = IngestionJobStatus.active.value
        job.progress = 100
        await db.commit()
        await db.refresh(sf)
        await db.refresh(version)
        await db.refresh(job)
        return sf, version, job
    except RagflowError as exc:
        job.status = IngestionJobStatus.failed.value
        job.error_code = exc.message_key
        job.error_message = exc.message
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
        job.status = IngestionJobStatus.parsing.value
        job.progress = 80
        activate_version(sf, version, None)
        job.status = IngestionJobStatus.active.value
        job.progress = 100
        await db.commit()
        await db.refresh(job)
        return job
    except RagflowError as exc:
        job.status = IngestionJobStatus.failed.value
        job.error_code = exc.message_key
        job.error_message = exc.message
        await db.commit()
        raise BadRequestError(message=exc.message, message_key=exc.message_key) from exc

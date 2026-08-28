"""Internal ingestion facade: authorization separated from ingestion core.

Member uploads and connector syncs share ingest_core; connectors must not forge a Member.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, BinaryIO

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.integrations.ragflow.exceptions import RagflowError, RagflowUploadUnknownError
from app.integrations.ragflow.upload_token import build_upload_token, deterministic_upload_filename
from app.models.base import not_deleted
from app.models.connector import ConnectorSourceObject
from app.models.enums import (
    ArchiveReason,
    AuditAction,
    IngestionJobStatus,
    KnowledgeActorType,
    KbPermission,
    SourceFileStatus,
    SourceKind,
    SourceSyncState,
)
from app.models.ingestion_job import IngestionJob
from app.models.knowledge_base import KnowledgeBase
from app.models.source_file import SourceFile
from app.models.source_file_version import SourceFileVersion
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_base_service, runtime_binding_service, source_file_service
from app.services.audit_service import write_audit
from app.services.metadata_service import build_meta_fields, validate_metadata_values
from app.services.permission_service import has_kb_permission
from app.services.source_file_service import next_version_no, sha256_bytes

# @lat: [[knowledge-objects#Connector Domain]]


@dataclass(frozen=True)
class KnowledgeActor:
    actor_type: str
    actor_id: str
    org_id: str
    member_id: str | None = None


def actor_from_member(member: KnowledgePrincipal) -> KnowledgeActor:
    return KnowledgeActor(
        actor_type=KnowledgeActorType.member.value,
        actor_id=member.member_id,
        org_id=member.org_id,
        member_id=member.member_id,
    )


def actor_from_connector(*, connector_id: str, org_id: str, member_id: str | None = None) -> KnowledgeActor:
    return KnowledgeActor(
        actor_type=KnowledgeActorType.connector.value,
        actor_id=connector_id,
        org_id=org_id,
        member_id=member_id,
    )


def _now() -> datetime:
    return datetime.now(UTC)


async def authorize_user_upload(
    db: AsyncSession,
    member: KnowledgePrincipal,
    kb_id: str,
) -> KnowledgeBase:
    kb = await knowledge_base_service.get_knowledge_base(db, member, kb_id)
    dataset_id = await runtime_binding_service.get_dataset_id(db, kb)
    if not dataset_id or kb.status != "active":
        raise BadRequestError(message="知识库未就绪", message_key="errors.knowledge.kb_not_ready")
    if not await has_kb_permission(db, member, kb.id, KbPermission.upload.value) and not await has_kb_permission(
        db, member, kb.id, KbPermission.manage.value
    ):
        raise ForbiddenError()
    return kb


def _ensure_not_connector_managed_for_manual_upload(sf: SourceFile) -> None:
    if sf.source_kind == SourceKind.connector.value and sf.connector_id:
        raise ConflictError(
            message="该源文件由 Connector 管理，禁止人工上传版本",
            message_key="errors.knowledge.source_managed_by_connector",
        )


async def ingest_from_member(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowRuntimeAdapter,
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
    kb = await authorize_user_upload(db, member, knowledge_base_id)
    if source_file_id:
        sf = await source_file_service.get_source_file(db, member, source_file_id)
        if sf.knowledge_base_id != knowledge_base_id:
            raise BadRequestError(message="源文件不属于该知识库", message_key="errors.knowledge.source_file_mismatch")
        _ensure_not_connector_managed_for_manual_upload(sf)
    return await ingest_core(
        db,
        ragflow,
        actor=actor_from_member(member),
        kb=kb,
        file_name=file_name,
        mime_type=mime_type,
        content=content,
        file_obj=file_obj,
        file_size=file_size,
        sha256=sha256,
        source_file_id=source_file_id,
        metadata=metadata,
        source_kind=SourceKind.manual.value,
        owner_member_id=member.member_id,
    )


async def ingest_from_connector(
    db: AsyncSession,
    ragflow: RagflowRuntimeAdapter,
    *,
    actor: KnowledgeActor,
    kb: KnowledgeBase,
    file_name: str,
    mime_type: str | None,
    content: bytes | None = None,
    file_obj: BinaryIO | None = None,
    file_size: int | None = None,
    sha256: str | None = None,
    source_file_id: str | None = None,
    metadata: dict | None = None,
    connector_id: str,
    external_object_id: str,
    source_uri: str | None = None,
    source_path: str | None = None,
    source_revision: str | None = None,
    source_etag: str | None = None,
    source_modified_at: datetime | None = None,
    source_metadata: dict[str, Any] | None = None,
    owner_member_id: str,
) -> tuple[SourceFile, SourceFileVersion, IngestionJob]:
    if actor.actor_type != KnowledgeActorType.connector.value:
        raise BadRequestError(message="Connector 入库必须使用 connector Actor", message_key="errors.common.bad_request")
    dataset_id = await runtime_binding_service.get_dataset_id(db, kb)
    if not dataset_id or kb.status != "active":
        raise BadRequestError(message="知识库未就绪", message_key="errors.knowledge.kb_not_ready")
    return await ingest_core(
        db,
        ragflow,
        actor=actor,
        kb=kb,
        file_name=file_name,
        mime_type=mime_type,
        content=content,
        file_obj=file_obj,
        file_size=file_size,
        sha256=sha256,
        source_file_id=source_file_id,
        metadata=metadata,
        source_kind=SourceKind.connector.value,
        owner_member_id=owner_member_id,
        connector_id=connector_id,
        external_object_id=external_object_id,
        source_uri=source_uri,
        source_path=source_path,
        source_revision=source_revision,
        source_etag=source_etag,
        source_modified_at=source_modified_at,
        source_metadata=source_metadata,
        sync_state=SourceSyncState.in_sync.value,
    )


async def ingest_core(
    db: AsyncSession,
    ragflow: RagflowRuntimeAdapter,
    *,
    actor: KnowledgeActor,
    kb: KnowledgeBase,
    file_name: str,
    mime_type: str | None,
    content: bytes | None = None,
    file_obj: BinaryIO | None = None,
    file_size: int | None = None,
    sha256: str | None = None,
    source_file_id: str | None = None,
    metadata: dict | None = None,
    source_kind: str = SourceKind.manual.value,
    owner_member_id: str,
    connector_id: str | None = None,
    external_object_id: str | None = None,
    source_uri: str | None = None,
    source_path: str | None = None,
    source_revision: str | None = None,
    source_etag: str | None = None,
    source_modified_at: datetime | None = None,
    source_metadata: dict[str, Any] | None = None,
    sync_state: str | None = None,
) -> tuple[SourceFile, SourceFileVersion, IngestionJob]:
    from app.services.ingestion_service import _validate_upload_size

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

    if actor.org_id != kb.org_id:
        raise ForbiddenError()

    dataset_id = await runtime_binding_service.require_dataset_id(db, kb)

    old_version: SourceFileVersion | None = None
    if source_file_id:
        sf = await db.get(SourceFile, source_file_id)
        if sf is None or sf.deleted_at is not None:
            raise NotFoundError(message="源文件不存在", message_key="errors.knowledge.source_file_not_found")
        if sf.knowledge_base_id != kb.id or sf.org_id != actor.org_id:
            raise BadRequestError(message="源文件不属于该知识库", message_key="errors.knowledge.source_file_mismatch")
        old_version = await db.get(SourceFileVersion, sf.active_version_id) if sf.active_version_id else None
        sf.status = SourceFileStatus.updating.value
        if metadata is not None:
            validated_metadata = validate_metadata_values(metadata, kb.metadata_schema, partial=False)
            sf.metadata_ = validated_metadata
            sf.metadata_revision = int(sf.metadata_revision or 0) + 1
        if source_kind == SourceKind.connector.value:
            sf.source_kind = SourceKind.connector.value
            sf.connector_id = connector_id
            sf.external_object_id = external_object_id
            sf.source_uri = source_uri
            sf.source_path = source_path
            sf.source_revision = source_revision
            sf.source_etag = source_etag
            sf.source_modified_at = source_modified_at
            sf.source_metadata = dict(source_metadata or {})
            sf.last_synced_at = _now()
            if sync_state:
                sf.sync_state = sync_state
    else:
        if source_kind == SourceKind.manual.value:
            existing = await db.execute(
                select(SourceFile).where(
                    SourceFile.knowledge_base_id == kb.id,
                    SourceFile.file_name == file_name,
                    SourceFile.connector_id.is_(None),
                    not_deleted(SourceFile),
                )
            )
            if existing.scalar_one_or_none():
                raise BadRequestError(message="同名文件已存在，请走版本更新", message_key="errors.knowledge.file_exists")
        validated_metadata = validate_metadata_values(metadata or {}, kb.metadata_schema, partial=False)
        sf = SourceFile(
            org_id=actor.org_id,
            knowledge_base_id=kb.id,
            file_name=file_name,
            mime_type=mime_type,
            owner_member_id=owner_member_id,
            status=SourceFileStatus.pending.value,
            metadata_=validated_metadata,
            metadata_revision=0,
            source_kind=source_kind,
            connector_id=connector_id,
            external_object_id=external_object_id,
            source_uri=source_uri,
            source_path=source_path,
            source_revision=source_revision,
            source_etag=source_etag,
            source_modified_at=source_modified_at,
            source_metadata=dict(source_metadata or {}),
            last_synced_at=_now() if source_kind == SourceKind.connector.value else None,
            sync_state=sync_state,
        )
        db.add(sf)
        await db.flush()

    version = SourceFileVersion(
        source_file_id=sf.id,
        version_no=await next_version_no(db, sf.id),
        file_size=size,
        sha256=digest,
        uploaded_by_member_id=actor.member_id if actor.actor_type == KnowledgeActorType.member.value else None,
        parse_status="pending",
        ragflow_status="UNSTART",
        origin_connector_id=connector_id if source_kind == SourceKind.connector.value else None,
        origin_external_revision=source_revision if source_kind == SourceKind.connector.value else None,
        origin_etag=source_etag if source_kind == SourceKind.connector.value else None,
        source_snapshot_at=_now() if source_kind == SourceKind.connector.value else None,
        created_by_actor_type=actor.actor_type,
        created_by_actor_id=actor.actor_id,
    )
    db.add(version)
    await db.flush()

    job_member_id = actor.member_id or owner_member_id
    job = IngestionJob(
        source_file_id=sf.id,
        file_version_id=version.id,
        status=IngestionJobStatus.pending.value,
        created_by_member_id=job_member_id,
    )
    db.add(job)
    await db.flush()

    try:
        job.status = IngestionJobStatus.uploading.value
        job.progress = 10
        await db.flush()

        upload_token = build_upload_token(source_file_id=sf.id, file_version_id=version.id)
        upload_name = deterministic_upload_filename(
            source_file_id=sf.id,
            file_version_id=version.id,
            original_name=file_name,
        )

        document_id: str | None = None
        try:
            if file_obj is not None:
                document_id = await ragflow.upload_document(
                    dataset_id,
                    filename=upload_name,
                    mime=mime_type,
                    file_obj=file_obj,
                    upload_token=upload_token,
                )
            else:
                document_id = await ragflow.upload_document(
                    dataset_id,
                    content or b"",
                    upload_name,
                    mime_type,
                    upload_token=upload_token,
                )
        except RagflowUploadUnknownError as exc:
            job.status = IngestionJobStatus.upload_unknown.value
            job.error_code = exc.message_key
            job.error_message = exc.message
            await db.flush()
            recovered = await ragflow.recover_uploaded_document(dataset_id, upload_token)
            if not recovered:
                job.status = IngestionJobStatus.failed.value
                job.finished_at = _now()
                version.parse_status = "failed"
                if old_version is None:
                    sf.status = SourceFileStatus.error.value
                else:
                    sf.status = SourceFileStatus.active.value
                await db.commit()
                raise BadRequestError(message=exc.message, message_key=exc.message_key) from exc
            document_id = recovered
            job.error_code = None
            job.error_message = None

        version.ragflow_document_id = document_id
        job.ragflow_document_id = document_id
        job.status = IngestionJobStatus.ragflow_uploaded.value
        job.progress = 40
        await db.flush()

        meta = build_meta_fields(
            source_file_id=sf.id,
            file_version_id=version.id,
            knowledge_base_id=kb.id,
            org_id=sf.org_id,
            metadata=sf.metadata_,
            metadata_revision=sf.metadata_revision,
            source_kind=sf.source_kind,
            connector_id=sf.connector_id,
            external_object_id=sf.external_object_id,
            source_revision=sf.source_revision,
        )
        meta["nk_upload_token"] = upload_token
        await ragflow.update_document_metadata(dataset_id, document_id, meta)
        job.status = IngestionJobStatus.metadata_synced.value
        job.progress = 60
        await db.flush()

        await ragflow.parse_documents(dataset_id, [document_id])
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
        if isinstance(exc, RagflowUploadUnknownError):
            raise
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


async def detach_source_file(
    db: AsyncSession,
    member: KnowledgePrincipal,
    source_file_id: str,
) -> SourceFile:
    sf = await source_file_service.get_source_file(db, member, source_file_id)
    if not await has_kb_permission(db, member, sf.knowledge_base_id, KbPermission.manage.value):
        raise ForbiddenError()
    if sf.source_kind != SourceKind.connector.value or not sf.connector_id:
        raise BadRequestError(
            message="仅 Connector 管理的源文件可以 detach",
            message_key="errors.knowledge.source_not_connector_managed",
        )

    connector_id = sf.connector_id
    external_object_id = sf.external_object_id

    result = await db.execute(
        select(ConnectorSourceObject).where(
            ConnectorSourceObject.connector_id == connector_id,
            ConnectorSourceObject.source_file_id == sf.id,
            not_deleted(ConnectorSourceObject),
        )
    )
    for obj in result.scalars().all():
        obj.source_file_id = None
        obj.state = "detached"

    if external_object_id:
        result2 = await db.execute(
            select(ConnectorSourceObject).where(
                ConnectorSourceObject.connector_id == connector_id,
                ConnectorSourceObject.external_object_id == external_object_id,
                not_deleted(ConnectorSourceObject),
            )
        )
        for obj in result2.scalars().all():
            if obj.source_file_id == sf.id or obj.source_file_id is None:
                obj.source_file_id = None
                obj.state = "detached"

    sf.source_kind = SourceKind.manual.value
    sf.connector_id = None
    sf.external_object_id = None
    sf.sync_state = SourceSyncState.detached.value
    sf.archive_reason = ArchiveReason.detached.value
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.source_detached.value,
        resource_type="source_file",
        resource_id=sf.id,
        details={},
    )
    await db.commit()
    await db.refresh(sf)
    return sf

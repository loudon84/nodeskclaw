"""SourceFile archive / unarchive and version rollback."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.enums import AuditAction, FilePermission, KbPermission, ParseStatus
from app.models.source_file import SourceFile
from app.models.source_file_version import SourceFileVersion
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_base_service, runtime_binding_service, source_file_service
from app.services.audit_service import write_audit
from app.services.permission_service import has_file_permission, has_kb_permission
from app.services.source_file_service import activate_version

logger = logging.getLogger(__name__)

_ACTIVATABLE_PARSE_STATUSES = {
    ParseStatus.active.value,
    ParseStatus.superseded.value,
}


async def _require_update_or_manage(
    db: AsyncSession,
    member: KnowledgePrincipal,
    sf: SourceFile,
) -> None:
    if await has_file_permission(db, member, sf, FilePermission.update.value):
        return
    if await has_kb_permission(db, member, sf.knowledge_base_id, KbPermission.manage.value):
        return
    raise ForbiddenError()


def _ensure_not_archived(sf: SourceFile) -> None:
    if sf.archived_at is not None:
        raise BadRequestError(
            message="源文件已归档",
            message_key="errors.knowledge.source_file_archived",
        )


async def archive_source_file(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowRuntimeAdapter,
    source_file_id: str,
) -> SourceFile:
    sf = await source_file_service.get_source_file(db, member, source_file_id)
    await _require_update_or_manage(db, member, sf)
    if sf.archived_at is None:
        sf.archived_at = datetime.now(UTC)

    kb = await knowledge_base_service.get_knowledge_base(db, member, sf.knowledge_base_id)
    dataset_id = await runtime_binding_service.get_dataset_id(db, kb)
    if dataset_id and sf.active_version_id:
        version = await db.get(SourceFileVersion, sf.active_version_id)
        if version and version.deleted_at is None and version.ragflow_document_id:
            try:
                await ragflow.set_document_enabled(dataset_id, version.ragflow_document_id, False)
            except Exception:
                logger.warning(
                    "failed to disable archived document dataset=%s document=%s",
                    dataset_id,
                    version.ragflow_document_id,
                )

    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.file_archive.value,
        resource_type="source_file",
        resource_id=sf.id,
        details={"active_version_id": sf.active_version_id},
    )
    await db.commit()
    await db.refresh(sf)
    return sf


async def unarchive_source_file(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowRuntimeAdapter,
    source_file_id: str,
) -> SourceFile:
    sf = await source_file_service.get_source_file(db, member, source_file_id)
    await _require_update_or_manage(db, member, sf)
    sf.archived_at = None

    kb = await knowledge_base_service.get_knowledge_base(db, member, sf.knowledge_base_id)
    dataset_id = await runtime_binding_service.get_dataset_id(db, kb)
    if dataset_id and sf.active_version_id:
        version = await db.get(SourceFileVersion, sf.active_version_id)
        if (
            version
            and version.deleted_at is None
            and version.ragflow_document_id
            and version.parse_status == ParseStatus.active.value
        ):
            try:
                await ragflow.set_document_enabled(dataset_id, version.ragflow_document_id, True)
            except Exception:
                logger.warning(
                    "failed to enable unarchived document dataset=%s document=%s",
                    dataset_id,
                    version.ragflow_document_id,
                )

    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.file_unarchive.value,
        resource_type="source_file",
        resource_id=sf.id,
        details={"active_version_id": sf.active_version_id},
    )
    await db.commit()
    await db.refresh(sf)
    return sf


async def activate_source_file_version(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowRuntimeAdapter,
    source_file_id: str,
    version_id: str,
) -> SourceFile:
    sf = await source_file_service.get_source_file(db, member, source_file_id)
    await _require_update_or_manage(db, member, sf)
    _ensure_not_archived(sf)

    target = await db.get(SourceFileVersion, version_id)
    if target is None or target.deleted_at is not None or target.source_file_id != source_file_id:
        raise NotFoundError(message="版本不存在", message_key="errors.knowledge.version_not_found")
    if target.parse_status not in _ACTIVATABLE_PARSE_STATUSES or not target.ragflow_document_id:
        raise BadRequestError(
            message="版本不可激活",
            message_key="errors.knowledge.version_not_activatable",
        )

    kb = await knowledge_base_service.get_knowledge_base(db, member, sf.knowledge_base_id)
    dataset_id = await runtime_binding_service.require_dataset_id(db, kb)

    await ragflow.set_document_enabled(dataset_id, target.ragflow_document_id, True)

    old_version = None
    if sf.active_version_id and sf.active_version_id != target.id:
        old_version = await db.get(SourceFileVersion, sf.active_version_id)

    activate_version(sf, target, old_version)
    from app.services import build_orchestrator

    try:
        await build_orchestrator.enqueue_after_activation(
            db,
            org_id=member.org_id,
            kb=kb,
            source_file_id=sf.id,
            version_id=target.id,
            capabilities=None,
            member_id=member.member_id,
        )
    except Exception:
        logger.exception(
            "build enqueue after activation failed kb=%s source=%s version=%s",
            kb.id,
            sf.id,
            target.id,
        )
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.file_version_activate.value,
        resource_type="source_file",
        resource_id=sf.id,
        details={
            "activated_version_id": target.id,
            "previous_version_id": old_version.id if old_version else None,
        },
    )
    await db.commit()
    await db.refresh(sf)

    if (
        old_version
        and old_version.ragflow_document_id
        and old_version.id != target.id
        and dataset_id
    ):
        try:
            await ragflow.set_document_enabled(dataset_id, old_version.ragflow_document_id, False)
        except Exception:
            logger.warning(
                "failed to disable superseded document dataset=%s document=%s",
                dataset_id,
                old_version.ragflow_document_id,
            )

    return sf

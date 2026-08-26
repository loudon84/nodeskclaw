"""Source file registry service (metadata + ACL + download auth)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.integrations.ragflow.client import RagflowClient
from app.models.base import not_deleted
from app.models.enums import AclEffect, AuditAction, FilePermission, KbPermission, SourceFileStatus
from app.models.source_file import SourceFile
from app.models.source_file_acl import SourceFileAcl
from app.models.source_file_version import SourceFileVersion
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_base_service, runtime_binding_service
from app.services.audit_service import write_audit
from app.services.permission_service import has_file_permission, has_kb_permission, validate_acl_subject


def _bump_file_acl_version(sf: SourceFile) -> None:
    sf.acl_version = (sf.acl_version or 1) + 1


async def list_source_files(
    db: AsyncSession,
    member: KnowledgePrincipal,
    knowledge_base_id: str,
    *,
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[SourceFile], int]:
    from app.services.permission_snapshot_service import load_permission_snapshot

    await knowledge_base_service.get_knowledge_base(db, member, knowledge_base_id)
    result = await db.execute(
        select(SourceFile).where(
            SourceFile.knowledge_base_id == knowledge_base_id,
            SourceFile.org_id == member.org_id,
            not_deleted(SourceFile),
        )
    )
    files = list(result.scalars().all())
    snapshot = await load_permission_snapshot(
        db,
        member,
        knowledge_base_ids=[knowledge_base_id],
        source_file_ids=[sf.id for sf in files],
        knowledge_set_ids=[],
    )
    out = [sf for sf in files if snapshot.has_file_permission(sf.id, FilePermission.read.value)]
    if q:
        q_lower = q.lower()
        out = [sf for sf in out if q_lower in (sf.file_name or "").lower()]
    sort_attr = sort_by if hasattr(SourceFile, sort_by) else "created_at"
    reverse = sort_order.lower() != "asc"
    out.sort(key=lambda sf: getattr(sf, sort_attr) or "", reverse=reverse)
    total = len(out)
    start = (page - 1) * page_size
    return out[start : start + page_size], total


async def list_global_source_files(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
    knowledge_base_id: str | None = None,
    parse_status: str | None = None,
    status: str | None = None,
    mime_type: str | None = None,
    owner_member_id: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[SourceFile], int]:
    from app.services.permission_snapshot_service import load_permission_snapshot

    snapshot = await load_permission_snapshot(db, member, knowledge_set_ids=[])
    readable_kb_ids = [
        kb_id for kb_id in snapshot.kb_owners if snapshot.has_kb_permission(kb_id, KbPermission.read.value)
    ]

    if knowledge_base_id:
        if knowledge_base_id not in readable_kb_ids:
            return [], 0
        readable_kb_ids = [knowledge_base_id]

    if not readable_kb_ids:
        return [], 0

    filters = [
        SourceFile.org_id == member.org_id,
        SourceFile.knowledge_base_id.in_(readable_kb_ids),
        not_deleted(SourceFile),
    ]
    if status:
        filters.append(SourceFile.status == status)
    if mime_type:
        filters.append(SourceFile.mime_type == mime_type)
    if owner_member_id:
        filters.append(SourceFile.owner_member_id == owner_member_id)
    if created_from:
        filters.append(SourceFile.created_at >= created_from)
    if created_to:
        filters.append(SourceFile.created_at <= created_to)
    if q:
        filters.append(SourceFile.file_name.ilike(f"%{q}%"))

    result = await db.execute(select(SourceFile).where(*filters))
    candidates = list(result.scalars().all())
    out = [sf for sf in candidates if snapshot.has_file_permission(sf.id, FilePermission.read.value)]

    if parse_status:
        filtered: list[SourceFile] = []
        for sf in out:
            if not sf.active_version_id:
                if parse_status == "pending":
                    filtered.append(sf)
                continue
            version = await db.get(SourceFileVersion, sf.active_version_id)
            if version and version.deleted_at is None and version.parse_status == parse_status:
                filtered.append(sf)
        out = filtered

    sort_attr = sort_by if hasattr(SourceFile, sort_by) else "created_at"
    reverse = sort_order.lower() != "asc"
    out.sort(key=lambda sf: getattr(sf, sort_attr) or "", reverse=reverse)
    total = len(out)
    start = (page - 1) * page_size
    return out[start : start + page_size], total


async def get_source_file(db: AsyncSession, member: KnowledgePrincipal, source_file_id: str) -> SourceFile:
    sf = await db.get(SourceFile, source_file_id)
    if sf is None or sf.deleted_at is not None or sf.org_id != member.org_id:
        raise NotFoundError(message="源文件不存在", message_key="errors.knowledge.source_file_not_found")
    if not await has_file_permission(db, member, sf, FilePermission.read.value):
        raise ForbiddenError()
    return sf


async def delete_source_file(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowClient,
    source_file_id: str,
) -> None:
    sf = await get_source_file(db, member, source_file_id)
    if not await has_file_permission(db, member, sf, FilePermission.delete.value):
        raise ForbiddenError()
    kb = await knowledge_base_service.get_knowledge_base(db, member, sf.knowledge_base_id)
    sf.status = SourceFileStatus.deleting.value
    sf.last_error = None
    await db.flush()

    versions = list(
        (
            await db.execute(
                select(SourceFileVersion).where(
                    SourceFileVersion.source_file_id == sf.id,
                    not_deleted(SourceFileVersion),
                )
            )
        ).scalars().all()
    )
    doc_ids = [v.ragflow_document_id for v in versions if v.ragflow_document_id]
    dataset_id = await runtime_binding_service.get_dataset_id(db, kb)
    if dataset_id and doc_ids:
        try:
            await ragflow.delete_documents(dataset_id, doc_ids)
        except Exception as exc:
            sf.last_error = str(exc)
            await db.commit()
            return
    for version in versions:
        version.soft_delete()
    sf.soft_delete()
    await db.commit()


async def next_version_no(db: AsyncSession, source_file_id: str) -> int:
    result = await db.execute(
        select(func.max(SourceFileVersion.version_no)).where(
            SourceFileVersion.source_file_id == source_file_id,
            not_deleted(SourceFileVersion),
        )
    )
    current = result.scalar_one_or_none() or 0
    return int(current) + 1


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


async def list_source_file_versions(
    db: AsyncSession,
    member: KnowledgePrincipal,
    source_file_id: str,
) -> list[SourceFileVersion]:
    await get_source_file(db, member, source_file_id)
    result = await db.execute(
        select(SourceFileVersion).where(
            SourceFileVersion.source_file_id == source_file_id,
            not_deleted(SourceFileVersion),
        ).order_by(SourceFileVersion.version_no.desc())
    )
    return list(result.scalars().all())


async def get_source_file_version(
    db: AsyncSession,
    member: KnowledgePrincipal,
    source_file_id: str,
    version_id: str,
) -> SourceFileVersion:
    await get_source_file(db, member, source_file_id)
    version = await db.get(SourceFileVersion, version_id)
    if version is None or version.deleted_at is not None or version.source_file_id != source_file_id:
        raise NotFoundError(message="版本不存在", message_key="errors.knowledge.version_not_found")
    return version


async def enrich_source_file(sf: SourceFile, db: AsyncSession) -> dict:
    data = {
        "id": sf.id,
        "org_id": sf.org_id,
        "knowledge_base_id": sf.knowledge_base_id,
        "file_name": sf.file_name,
        "mime_type": sf.mime_type,
        "owner_member_id": sf.owner_member_id,
        "active_version_id": sf.active_version_id,
        "status": sf.status,
        "acl_version": sf.acl_version,
        "parse_status": None,
        "chunk_count": None,
        "version_no": None,
    }
    if sf.active_version_id:
        version = await db.get(SourceFileVersion, sf.active_version_id)
        if version and version.deleted_at is None:
            data["parse_status"] = version.parse_status
            data["chunk_count"] = version.chunk_count
            data["version_no"] = version.version_no
    return data


async def download_source_file(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowClient,
    source_file_id: str,
) -> tuple[SourceFile, SourceFileVersion, bytes]:
    sf = await get_source_file(db, member, source_file_id)
    if not await has_file_permission(db, member, sf, FilePermission.download.value):
        raise ForbiddenError(message="无下载权限", message_key="errors.knowledge.download_forbidden")
    if not sf.active_version_id:
        raise NotFoundError(message="没有可用版本", message_key="errors.knowledge.version_not_found")
    version = await db.get(SourceFileVersion, sf.active_version_id)
    if version is None or version.deleted_at is not None or not version.ragflow_document_id:
        raise NotFoundError(message="没有可用版本", message_key="errors.knowledge.version_not_found")
    kb = await knowledge_base_service.get_knowledge_base(db, member, sf.knowledge_base_id)
    dataset_id = await runtime_binding_service.get_dataset_id(db, kb)
    if not dataset_id:
        raise NotFoundError(message="知识库未就绪", message_key="errors.knowledge.kb_not_ready")
    content = await ragflow.download_document(dataset_id, version.ragflow_document_id)
    return sf, version, content


async def list_file_acl(db: AsyncSession, member: KnowledgePrincipal, source_file_id: str) -> list[SourceFileAcl]:
    await get_source_file(db, member, source_file_id)
    result = await db.execute(
        select(SourceFileAcl).where(
            SourceFileAcl.source_file_id == source_file_id,
            not_deleted(SourceFileAcl),
        )
    )
    return list(result.scalars().all())


async def add_file_acl(
    db: AsyncSession,
    member: KnowledgePrincipal,
    source_file_id: str,
    *,
    subject_type: str,
    subject_id: str,
    permission: str,
    effect: str = AclEffect.allow.value,
) -> SourceFileAcl:
    sf = await get_source_file(db, member, source_file_id)
    if not await has_file_permission(db, member, sf, FilePermission.manage_acl.value) and not await has_kb_permission(
        db, member, sf.knowledge_base_id, KbPermission.manage_acl.value
    ):
        raise ForbiddenError()
    validate_acl_subject(member, subject_type=subject_type, subject_id=subject_id)
    row = SourceFileAcl(
        source_file_id=source_file_id,
        subject_type=subject_type,
        subject_id=subject_id,
        permission=permission,
        effect=effect,
        created_by_member_id=member.member_id,
    )
    db.add(row)
    _bump_file_acl_version(sf)
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.file_acl_add.value,
        resource_type="source_file",
        resource_id=source_file_id,
        details={
            "subject_type": subject_type,
            "subject_id": subject_id,
            "permission": permission,
            "effect": effect,
            "acl_version": sf.acl_version,
        },
    )
    await db.commit()
    await db.refresh(row)
    return row


async def delete_file_acl(
    db: AsyncSession,
    member: KnowledgePrincipal,
    source_file_id: str,
    acl_id: str,
) -> None:
    sf = await get_source_file(db, member, source_file_id)
    if not await has_file_permission(db, member, sf, FilePermission.manage_acl.value) and not await has_kb_permission(
        db, member, sf.knowledge_base_id, KbPermission.manage_acl.value
    ):
        raise ForbiddenError()
    acl = await db.get(SourceFileAcl, acl_id)
    if acl is None or acl.deleted_at is not None or acl.source_file_id != source_file_id:
        raise NotFoundError(message="ACL 不存在", message_key="errors.knowledge.acl_not_found")
    acl.soft_delete()
    _bump_file_acl_version(sf)
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.file_acl_delete.value,
        resource_type="source_file",
        resource_id=source_file_id,
        details={
            "acl_id": acl_id,
            "subject_type": acl.subject_type,
            "subject_id": acl.subject_id,
            "permission": acl.permission,
            "acl_version": sf.acl_version,
        },
    )
    await db.commit()


def activate_version(sf: SourceFile, new_version: SourceFileVersion, old_version: SourceFileVersion | None) -> None:
    now = datetime.now(UTC)
    new_version.parse_status = "active"
    new_version.activated_at = now
    sf.active_version_id = new_version.id
    sf.status = SourceFileStatus.active.value
    if old_version and old_version.id != new_version.id:
        old_version.parse_status = "superseded"
        old_version.superseded_at = now

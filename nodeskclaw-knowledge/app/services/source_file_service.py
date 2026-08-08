"""Source file registry service (metadata + ACL + download auth)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.integrations.ragflow.client import RagflowClient
from app.models.base import not_deleted
from app.models.enums import AclEffect, FilePermission, KbPermission, SourceFileStatus
from app.models.source_file import SourceFile
from app.models.source_file_acl import SourceFileAcl
from app.models.source_file_version import SourceFileVersion
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_base_service
from app.services.permission_service import has_file_permission, has_kb_permission


async def list_source_files(
    db: AsyncSession,
    member: KnowledgePrincipal,
    knowledge_base_id: str,
) -> list[SourceFile]:
    await knowledge_base_service.get_knowledge_base(db, member, knowledge_base_id)
    result = await db.execute(
        select(SourceFile).where(
            SourceFile.knowledge_base_id == knowledge_base_id,
            SourceFile.org_id == member.org_id,
            not_deleted(SourceFile),
        ).order_by(SourceFile.created_at.desc())
    )
    files = list(result.scalars().all())
    out: list[SourceFile] = []
    for sf in files:
        if await has_file_permission(db, member, sf, FilePermission.read.value):
            out.append(sf)
    return out


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
    versions = await db.execute(
        select(SourceFileVersion).where(
            SourceFileVersion.source_file_id == sf.id,
            not_deleted(SourceFileVersion),
        )
    )
    doc_ids = [v.ragflow_document_id for v in versions.scalars().all() if v.ragflow_document_id]
    if kb.ragflow_dataset_id and doc_ids:
        try:
            await ragflow.delete_documents(kb.ragflow_dataset_id, doc_ids)
        except Exception:
            pass
    for version in (await db.execute(
        select(SourceFileVersion).where(
            SourceFileVersion.source_file_id == sf.id,
            not_deleted(SourceFileVersion),
        )
    )).scalars().all():
        version.soft_delete()
    sf.status = SourceFileStatus.deleting.value
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
    if not kb.ragflow_dataset_id:
        raise NotFoundError(message="知识库未就绪", message_key="errors.knowledge.kb_not_ready")
    content = await ragflow.download_document(kb.ragflow_dataset_id, version.ragflow_document_id)
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
    row = SourceFileAcl(
        source_file_id=source_file_id,
        subject_type=subject_type,
        subject_id=subject_id,
        permission=permission,
        effect=effect,
        created_by_member_id=member.member_id,
    )
    db.add(row)
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

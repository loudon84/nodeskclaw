"""ACL AccessPlan computation."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.models.enums import AccessPlanKind, AclEffect, FilePermission, KbPermission, SubjectType
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_base_acl import KnowledgeBaseAcl
from app.models.source_file import SourceFile
from app.models.source_file_acl import SourceFileAcl
from app.models.source_file_version import SourceFileVersion
from app.schemas.principal import KnowledgePrincipal

_SUBJECT_RANK = {
    SubjectType.organization.value: 10,
    SubjectType.department.value: 20,
    SubjectType.role.value: 20,
    SubjectType.member.value: 30,
}


@dataclass
class AccessPlan:
    kind: AccessPlanKind
    dataset_ids: list[str] = field(default_factory=list)
    document_ids: list[str] = field(default_factory=list)
    source_file_ids: list[str] = field(default_factory=list)
    knowledge_base_ids: list[str] = field(default_factory=list)


def _subject_matches(acl: KnowledgeBaseAcl | SourceFileAcl, member: KnowledgePrincipal) -> bool:
    if acl.subject_type == SubjectType.organization.value:
        return acl.subject_id in {"*", member.org_id}
    if acl.subject_type == SubjectType.department.value:
        return bool(member.department) and acl.subject_id == member.department
    if acl.subject_type == SubjectType.role.value:
        return acl.subject_id == member.member_role
    if acl.subject_type == SubjectType.member.value:
        return acl.subject_id == member.member_id
    return False


def _resolve_permission(acls: list, member: KnowledgePrincipal, permission: str) -> bool | None:
    """Return True/False if decided, None if no matching rule."""
    matched = [a for a in acls if a.permission == permission and _subject_matches(a, member)]
    if not matched:
        return None
    denies = [a for a in matched if a.effect == AclEffect.deny.value]
    if denies:
        return False
    allows = [a for a in matched if a.effect == AclEffect.allow.value]
    if not allows:
        return None
    allows.sort(key=lambda a: _SUBJECT_RANK.get(a.subject_type, 0), reverse=True)
    return True


async def has_kb_permission(
    db: AsyncSession,
    member: KnowledgePrincipal,
    knowledge_base_id: str,
    permission: str,
) -> bool:
    if member.is_super_admin:
        return True
    result = await db.execute(
        select(KnowledgeBaseAcl).where(
            KnowledgeBaseAcl.knowledge_base_id == knowledge_base_id,
            not_deleted(KnowledgeBaseAcl),
        )
    )
    acls = list(result.scalars().all())
    decided = _resolve_permission(acls, member, permission)
    if decided is not None:
        return decided
    if permission != KbPermission.read.value:
        manage = _resolve_permission(acls, member, KbPermission.manage.value)
        if manage:
            return True
    return False


async def has_file_permission(
    db: AsyncSession,
    member: KnowledgePrincipal,
    source_file: SourceFile,
    permission: str,
) -> bool:
    if member.is_super_admin:
        return True
    result = await db.execute(
        select(SourceFileAcl).where(
            SourceFileAcl.source_file_id == source_file.id,
            not_deleted(SourceFileAcl),
        )
    )
    file_acls = list(result.scalars().all())
    decided = _resolve_permission(file_acls, member, permission)
    if decided is not None:
        return decided
    kb_perm = FilePermission.read.value if permission == FilePermission.download.value else permission
    if kb_perm not in {p.value for p in KbPermission}:
        kb_perm = KbPermission.read.value
    return await has_kb_permission(db, member, source_file.knowledge_base_id, kb_perm)


async def build_access_plan(
    db: AsyncSession,
    member: KnowledgePrincipal,
    knowledge_bases: list[KnowledgeBase],
) -> AccessPlan:
    readable_kbs: list[KnowledgeBase] = []
    for kb in knowledge_bases:
        if await has_kb_permission(db, member, kb.id, KbPermission.read.value):
            readable_kbs.append(kb)

    if not readable_kbs:
        return AccessPlan(kind=AccessPlanKind.no_access)

    full_dataset_ids: list[str] = []
    filtered_document_ids: list[str] = []
    allowed_source_file_ids: list[str] = []
    any_filtered = False

    for kb in readable_kbs:
        if not kb.ragflow_dataset_id:
            continue
        result = await db.execute(
            select(SourceFile).where(
                SourceFile.knowledge_base_id == kb.id,
                SourceFile.org_id == member.org_id,
                not_deleted(SourceFile),
            )
        )
        files = list(result.scalars().all())
        denied_or_partial = False
        kb_allowed_files: list[SourceFile] = []
        for sf in files:
            if await has_file_permission(db, member, sf, FilePermission.read.value):
                kb_allowed_files.append(sf)
            else:
                denied_or_partial = True

        if not files:
            full_dataset_ids.append(kb.ragflow_dataset_id)
            continue

        if not denied_or_partial and len(kb_allowed_files) == len(files):
            full_dataset_ids.append(kb.ragflow_dataset_id)
            allowed_source_file_ids.extend([f.id for f in kb_allowed_files])
            continue

        any_filtered = True
        for sf in kb_allowed_files:
            allowed_source_file_ids.append(sf.id)
            if not sf.active_version_id:
                continue
            version = await db.get(SourceFileVersion, sf.active_version_id)
            if version and version.ragflow_document_id and version.deleted_at is None:
                filtered_document_ids.append(version.ragflow_document_id)

    kind = AccessPlanKind.filtered_access if any_filtered else AccessPlanKind.full_access
    dataset_ids = list(dict.fromkeys(full_dataset_ids + ([kb.ragflow_dataset_id for kb in readable_kbs if kb.ragflow_dataset_id] if any_filtered else [])))
    if any_filtered:
        dataset_ids = list(dict.fromkeys([kb.ragflow_dataset_id for kb in readable_kbs if kb.ragflow_dataset_id]))

    return AccessPlan(
        kind=kind,
        dataset_ids=dataset_ids,
        document_ids=list(dict.fromkeys(filtered_document_ids)) if any_filtered else [],
        source_file_ids=list(dict.fromkeys(allowed_source_file_ids)),
        knowledge_base_ids=[kb.id for kb in readable_kbs],
    )

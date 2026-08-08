"""ACL AccessPlan / Set permission computation."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError
from app.models.base import not_deleted
from app.models.enums import (
    AccessPlanKind,
    AclEffect,
    FilePermission,
    KbPermission,
    SetPermission,
    SubjectType,
)
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_base_acl import KnowledgeBaseAcl
from app.models.knowledge_set import KnowledgeSet
from app.models.knowledge_set_acl import KnowledgeSetAcl
from app.models.source_file import SourceFile
from app.models.source_file_acl import SourceFileAcl
from app.models.source_file_version import SourceFileVersion
from app.schemas.principal import KnowledgePrincipal
from app.services.acl_templates import ALLOWED_MEMBER_ROLES

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
    full_dataset_ids: list[str] = field(default_factory=list)
    partial_slices: list[dict] = field(default_factory=list)


def validate_acl_subject(
    member: KnowledgePrincipal,
    *,
    subject_type: str,
    subject_id: str,
) -> None:
    if subject_type == SubjectType.member.value:
        if not subject_id:
            raise BadRequestError(message="无效的 member subject", message_key="errors.knowledge.acl_subject_invalid")
        return
    if subject_type == SubjectType.role.value:
        if subject_id not in ALLOWED_MEMBER_ROLES:
            raise BadRequestError(
                message="role 仅允许 member/operator/admin",
                message_key="errors.knowledge.acl_role_invalid",
            )
        return
    if subject_type == SubjectType.department.value:
        if not subject_id:
            raise BadRequestError(
                message="无效的 department subject",
                message_key="errors.knowledge.acl_subject_invalid",
            )
        return
    if subject_type == SubjectType.organization.value:
        if subject_id not in {"*", member.org_id}:
            raise BadRequestError(
                message="organization subject 只能是当前组织",
                message_key="errors.knowledge.acl_org_invalid",
            )
        return
    raise BadRequestError(message="无效 subject_type", message_key="errors.knowledge.acl_subject_invalid")


def _subject_matches(acl: KnowledgeBaseAcl | SourceFileAcl | KnowledgeSetAcl, member: KnowledgePrincipal) -> bool:
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
    kb = await db.get(KnowledgeBase, knowledge_base_id)
    if kb and kb.deleted_at is None and kb.owner_member_id == member.member_id:
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
    if source_file.owner_member_id == member.member_id:
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


async def has_set_permission(
    db: AsyncSession,
    member: KnowledgePrincipal,
    knowledge_set: KnowledgeSet | str,
    permission: str,
) -> bool:
    if member.is_super_admin:
        return True
    if isinstance(knowledge_set, str):
        ks = await db.get(KnowledgeSet, knowledge_set)
    else:
        ks = knowledge_set
    if ks is None or ks.deleted_at is not None:
        return False
    if ks.owner_member_id == member.member_id:
        return True
    result = await db.execute(
        select(KnowledgeSetAcl).where(
            KnowledgeSetAcl.knowledge_set_id == ks.id,
            not_deleted(KnowledgeSetAcl),
        )
    )
    acls = list(result.scalars().all())
    decided = _resolve_permission(acls, member, permission)
    if decided is not None:
        return decided
    if permission != SetPermission.read.value:
        manage = _resolve_permission(acls, member, SetPermission.manage.value)
        if manage:
            return True
    return False


async def build_access_plan(
    db: AsyncSession,
    member: KnowledgePrincipal,
    knowledge_bases: list[KnowledgeBase],
) -> AccessPlan:
    readable_kbs: list[KnowledgeBase] = []
    for kb in knowledge_bases:
        if kb.status == "deleting":
            continue
        if await has_kb_permission(db, member, kb.id, KbPermission.read.value):
            readable_kbs.append(kb)

    if not readable_kbs:
        return AccessPlan(kind=AccessPlanKind.no_access)

    full_dataset_ids: list[str] = []
    filtered_document_ids: list[str] = []
    allowed_source_file_ids: list[str] = []
    partial_slices: list[dict] = []
    any_filtered = False

    for kb in readable_kbs:
        if not kb.ragflow_dataset_id:
            continue
        result = await db.execute(
            select(SourceFile).where(
                SourceFile.knowledge_base_id == kb.id,
                SourceFile.org_id == member.org_id,
                SourceFile.status != "deleting",
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

        if not files or (not denied_or_partial and len(kb_allowed_files) == len(files)):
            full_dataset_ids.append(kb.ragflow_dataset_id)
            allowed_source_file_ids.extend([f.id for f in kb_allowed_files])
            continue

        any_filtered = True
        doc_ids: list[str] = []
        for sf in kb_allowed_files:
            allowed_source_file_ids.append(sf.id)
            if not sf.active_version_id:
                continue
            version = await db.get(SourceFileVersion, sf.active_version_id)
            if version and version.ragflow_document_id and version.deleted_at is None:
                filtered_document_ids.append(version.ragflow_document_id)
                doc_ids.append(version.ragflow_document_id)
        if doc_ids:
            partial_slices.append(
                {
                    "kind": "filtered_documents",
                    "dataset_id": kb.ragflow_dataset_id,
                    "knowledge_base_id": kb.id,
                    "document_ids": doc_ids,
                }
            )

    kind = AccessPlanKind.filtered_access if any_filtered else AccessPlanKind.full_access
    dataset_ids = list(dict.fromkeys(full_dataset_ids))
    if any_filtered:
        dataset_ids = list(
            dict.fromkeys(
                full_dataset_ids
                + [s["dataset_id"] for s in partial_slices]
            )
        )

    return AccessPlan(
        kind=kind,
        dataset_ids=dataset_ids,
        document_ids=list(dict.fromkeys(filtered_document_ids)) if any_filtered else [],
        source_file_ids=list(dict.fromkeys(allowed_source_file_ids)),
        knowledge_base_ids=[kb.id for kb in readable_kbs],
        full_dataset_ids=list(dict.fromkeys(full_dataset_ids)),
        partial_slices=partial_slices,
    )

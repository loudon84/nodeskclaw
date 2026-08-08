"""Batch ACL loading and O(1) permission checks."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.models.enums import FilePermission, KbPermission, SetPermission
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_base_acl import KnowledgeBaseAcl
from app.models.knowledge_set import KnowledgeSet
from app.models.knowledge_set_acl import KnowledgeSetAcl
from app.models.source_file import SourceFile
from app.models.source_file_acl import SourceFileAcl
from app.schemas.principal import KnowledgePrincipal
from app.services.permission_service import _resolve_permission


@dataclass
class PermissionSnapshot:
    member: KnowledgePrincipal
    kb_acls: dict[str, list[KnowledgeBaseAcl]] = field(default_factory=dict)
    file_acls: dict[str, list[SourceFileAcl]] = field(default_factory=dict)
    set_acls: dict[str, list[KnowledgeSetAcl]] = field(default_factory=dict)
    kb_owners: dict[str, str] = field(default_factory=dict)
    file_owners: dict[str, str] = field(default_factory=dict)
    set_owners: dict[str, str] = field(default_factory=dict)
    file_kb_ids: dict[str, str] = field(default_factory=dict)

    def has_kb_permission(self, knowledge_base_id: str, permission: str) -> bool:
        if self.member.is_super_admin:
            return True
        if self.kb_owners.get(knowledge_base_id) == self.member.member_id:
            return True
        acls = self.kb_acls.get(knowledge_base_id, [])
        decided = _resolve_permission(acls, self.member, permission)
        if decided is not None:
            return decided
        if permission != KbPermission.read.value:
            manage = _resolve_permission(acls, self.member, KbPermission.manage.value)
            if manage:
                return True
        return False

    def has_file_permission(self, source_file_id: str, permission: str) -> bool:
        if self.member.is_super_admin:
            return True
        if self.file_owners.get(source_file_id) == self.member.member_id:
            return True
        acls = self.file_acls.get(source_file_id, [])
        decided = _resolve_permission(acls, self.member, permission)
        if decided is not None:
            return decided
        kb_id = self.file_kb_ids.get(source_file_id)
        if not kb_id:
            return False
        kb_perm = FilePermission.read.value if permission == FilePermission.download.value else permission
        if kb_perm not in {p.value for p in KbPermission}:
            kb_perm = KbPermission.read.value
        return self.has_kb_permission(kb_id, kb_perm)

    def has_set_permission(self, knowledge_set_id: str, permission: str) -> bool:
        if self.member.is_super_admin:
            return True
        if self.set_owners.get(knowledge_set_id) == self.member.member_id:
            return True
        acls = self.set_acls.get(knowledge_set_id, [])
        decided = _resolve_permission(acls, self.member, permission)
        if decided is not None:
            return decided
        if permission != SetPermission.read.value:
            manage = _resolve_permission(acls, self.member, SetPermission.manage.value)
            if manage:
                return True
        return False


async def load_permission_snapshot(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    knowledge_base_ids: list[str] | None = None,
    source_file_ids: list[str] | None = None,
    knowledge_set_ids: list[str] | None = None,
) -> PermissionSnapshot:
    snapshot = PermissionSnapshot(member=member)

    kb_query = select(KnowledgeBase).where(
        KnowledgeBase.org_id == member.org_id,
        not_deleted(KnowledgeBase),
    )
    if knowledge_base_ids is not None:
        if not knowledge_base_ids:
            kbs: list[KnowledgeBase] = []
        else:
            kb_query = kb_query.where(KnowledgeBase.id.in_(knowledge_base_ids))
            kbs = list((await db.execute(kb_query)).scalars().all())
    else:
        kbs = list((await db.execute(kb_query)).scalars().all())
    kb_ids = [kb.id for kb in kbs]
    snapshot.kb_owners = {kb.id: kb.owner_member_id for kb in kbs}

    if kb_ids:
        kb_acl_rows = await db.execute(
            select(KnowledgeBaseAcl).where(
                KnowledgeBaseAcl.knowledge_base_id.in_(kb_ids),
                not_deleted(KnowledgeBaseAcl),
            )
        )
        for acl in kb_acl_rows.scalars().all():
            snapshot.kb_acls.setdefault(acl.knowledge_base_id, []).append(acl)

    file_query = select(SourceFile).where(
        SourceFile.org_id == member.org_id,
        not_deleted(SourceFile),
    )
    if source_file_ids is not None:
        if not source_file_ids:
            files: list[SourceFile] = []
        else:
            file_query = file_query.where(SourceFile.id.in_(source_file_ids))
            files = list((await db.execute(file_query)).scalars().all())
    elif knowledge_base_ids is not None:
        if not kb_ids:
            files = []
        else:
            file_query = file_query.where(SourceFile.knowledge_base_id.in_(kb_ids))
            files = list((await db.execute(file_query)).scalars().all())
    else:
        files = list((await db.execute(file_query)).scalars().all())

    file_ids = [sf.id for sf in files]
    snapshot.file_owners = {sf.id: sf.owner_member_id for sf in files}
    snapshot.file_kb_ids = {sf.id: sf.knowledge_base_id for sf in files}

    missing_kb_ids = sorted({sf.knowledge_base_id for sf in files if sf.knowledge_base_id not in snapshot.kb_owners})
    if missing_kb_ids:
        extra_kbs = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id.in_(missing_kb_ids),
                not_deleted(KnowledgeBase),
            )
        )
        for kb in extra_kbs.scalars().all():
            snapshot.kb_owners[kb.id] = kb.owner_member_id
        extra_kb_acls = await db.execute(
            select(KnowledgeBaseAcl).where(
                KnowledgeBaseAcl.knowledge_base_id.in_(missing_kb_ids),
                not_deleted(KnowledgeBaseAcl),
            )
        )
        for acl in extra_kb_acls.scalars().all():
            snapshot.kb_acls.setdefault(acl.knowledge_base_id, []).append(acl)

    if file_ids:
        file_acl_rows = await db.execute(
            select(SourceFileAcl).where(
                SourceFileAcl.source_file_id.in_(file_ids),
                not_deleted(SourceFileAcl),
            )
        )
        for acl in file_acl_rows.scalars().all():
            snapshot.file_acls.setdefault(acl.source_file_id, []).append(acl)

    set_query = select(KnowledgeSet).where(
        KnowledgeSet.org_id == member.org_id,
        not_deleted(KnowledgeSet),
    )
    if knowledge_set_ids is not None:
        if not knowledge_set_ids:
            sets: list[KnowledgeSet] = []
        else:
            set_query = set_query.where(KnowledgeSet.id.in_(knowledge_set_ids))
            sets = list((await db.execute(set_query)).scalars().all())
    else:
        sets = list((await db.execute(set_query)).scalars().all())
    set_ids = [ks.id for ks in sets]
    snapshot.set_owners = {ks.id: ks.owner_member_id for ks in sets}

    if set_ids:
        set_acl_rows = await db.execute(
            select(KnowledgeSetAcl).where(
                KnowledgeSetAcl.knowledge_set_id.in_(set_ids),
                not_deleted(KnowledgeSetAcl),
            )
        )
        for acl in set_acl_rows.scalars().all():
            snapshot.set_acls.setdefault(acl.knowledge_set_id, []).append(acl)

    return snapshot

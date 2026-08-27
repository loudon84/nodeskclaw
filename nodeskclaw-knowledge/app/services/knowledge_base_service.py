"""KnowledgeBase CRUD service."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.integrations.ragflow.exceptions import RagflowError
from app.models.base import not_deleted
from app.models.enums import AclEffect, AuditAction, KnowledgeBaseStatus, KbPermission, SubjectType, UiRole
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_base_acl import KnowledgeBaseAcl
from app.schemas.principal import KnowledgePrincipal
from app.services.acl_templates import KB_ROLE_PERMISSIONS, visibility_acl_specs
from app.services.audit_service import write_audit
from app.services.permission_service import has_kb_permission, validate_acl_subject


def _bump_kb_acl_version(kb: KnowledgeBase) -> None:
    kb.acl_version = (kb.acl_version or 1) + 1


def _seed_visibility_acl(
    db: AsyncSession,
    *,
    knowledge_base_id: str,
    visibility: str,
    member: KnowledgePrincipal,
) -> None:
    specs = visibility_acl_specs(
        visibility,
        org_id=member.org_id,
        department=member.department,
        permissions=[KbPermission.read.value],
    )
    for subject_type, subject_id, permission in specs:
        db.add(
            KnowledgeBaseAcl(
                knowledge_base_id=knowledge_base_id,
                subject_type=subject_type,
                subject_id=subject_id,
                permission=permission,
                effect=AclEffect.allow.value,
                created_by_member_id=member.member_id,
            )
        )


def expand_kb_role_permissions(role: str) -> list[str]:
    if role == UiRole.owner.value:
        return KB_ROLE_PERMISSIONS[UiRole.manager.value]
    if role not in KB_ROLE_PERMISSIONS:
        raise BadRequestError(message="无效 UI 角色", message_key="errors.knowledge.acl_role_invalid")
    return KB_ROLE_PERMISSIONS[role]


async def list_knowledge_bases(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
    status: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[KnowledgeBase], int]:
    from app.services.permission_snapshot_service import load_permission_snapshot

    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.org_id == member.org_id,
            not_deleted(KnowledgeBase),
        )
    )
    items = list(result.scalars().all())
    snapshot = await load_permission_snapshot(
        db,
        member,
        knowledge_base_ids=[kb.id for kb in items],
        knowledge_set_ids=[],
        source_file_ids=[],
    )
    out = [kb for kb in items if snapshot.has_kb_permission(kb.id, KbPermission.read.value)]
    if status:
        out = [kb for kb in out if kb.status == status]
    if q:
        q_lower = q.lower()
        out = [
            kb
            for kb in out
            if q_lower in (kb.name or "").lower()
            or q_lower in (kb.description or "").lower()
        ]
    sort_attr = sort_by if hasattr(KnowledgeBase, sort_by) else "created_at"
    reverse = sort_order.lower() != "asc"
    out.sort(key=lambda kb: getattr(kb, sort_attr) or "", reverse=reverse)
    total = len(out)
    start = (page - 1) * page_size
    return out[start : start + page_size], total


async def get_knowledge_base(db: AsyncSession, member: KnowledgePrincipal, kb_id: str) -> KnowledgeBase:
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None or kb.deleted_at is not None or kb.org_id != member.org_id:
        raise NotFoundError(message="知识库不存在", message_key="errors.knowledge.kb_not_found")
    if not await has_kb_permission(db, member, kb.id, KbPermission.read.value):
        raise ForbiddenError()
    return kb


async def create_knowledge_base(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowRuntimeAdapter,
    *,
    name: str,
    description: str | None,
    embedding_model: str,
    chunk_method: str,
    parser_config: dict | None,
    visibility: str,
    tags: list[str] | None = None,
) -> KnowledgeBase:
    existing = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.org_id == member.org_id,
            KnowledgeBase.name == name,
            not_deleted(KnowledgeBase),
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(message="知识库名称已存在", message_key="errors.knowledge.kb_name_exists")

    kb = KnowledgeBase(
        org_id=member.org_id,
        name=name,
        description=description,
        embedding_model=embedding_model,
        chunk_method=chunk_method,
        parser_config=parser_config,
        owner_member_id=member.member_id,
        status=KnowledgeBaseStatus.provisioning.value,
        visibility=visibility,
        tags=tags,
    )
    db.add(kb)
    await db.flush()

    db.add(
        KnowledgeBaseAcl(
            knowledge_base_id=kb.id,
            subject_type=SubjectType.member.value,
            subject_id=member.member_id,
            permission=KbPermission.manage.value,
            effect=AclEffect.allow.value,
            created_by_member_id=member.member_id,
        )
    )
    db.add(
        KnowledgeBaseAcl(
            knowledge_base_id=kb.id,
            subject_type=SubjectType.member.value,
            subject_id=member.member_id,
            permission=KbPermission.read.value,
            effect=AclEffect.allow.value,
            created_by_member_id=member.member_id,
        )
    )
    db.add(
        KnowledgeBaseAcl(
            knowledge_base_id=kb.id,
            subject_type=SubjectType.member.value,
            subject_id=member.member_id,
            permission=KbPermission.upload.value,
            effect=AclEffect.allow.value,
            created_by_member_id=member.member_id,
        )
    )
    db.add(
        KnowledgeBaseAcl(
            knowledge_base_id=kb.id,
            subject_type=SubjectType.member.value,
            subject_id=member.member_id,
            permission=KbPermission.manage_acl.value,
            effect=AclEffect.allow.value,
            created_by_member_id=member.member_id,
        )
    )
    _seed_visibility_acl(db, knowledge_base_id=kb.id, visibility=visibility, member=member)

    try:
        adapter = ragflow
        result = await adapter.provision_binding(
            db,
            kb=kb,
            embedding_model=embedding_model,
            chunk_method=chunk_method,
            parser_config=parser_config,
            description=description,
            name=f"{member.org_id}:{name}",
            org_id=member.org_id,
        )
        kb.ragflow_dataset_id = result.resource_id
        kb.status = KnowledgeBaseStatus.active.value
    except RagflowError as exc:
        kb.status = KnowledgeBaseStatus.error.value
        await db.commit()
        raise BadRequestError(message=exc.message, message_key=exc.message_key) from exc

    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.kb_create.value,
        resource_type="knowledge_base",
        resource_id=kb.id,
        details={"name": name, "visibility": visibility},
    )
    await db.commit()
    await db.refresh(kb)
    return kb


async def update_knowledge_base(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowRuntimeAdapter,
    kb_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    embedding_model: str | None = None,
) -> KnowledgeBase:
    kb = await get_knowledge_base(db, member, kb_id)
    if not await has_kb_permission(db, member, kb.id, KbPermission.update.value) and not await has_kb_permission(
        db, member, kb.id, KbPermission.manage.value
    ):
        raise ForbiddenError()
    if embedding_model is not None and embedding_model != kb.embedding_model:
        from app.models.source_file import SourceFile

        file_count = await db.scalar(
            select(func.count())
            .select_from(SourceFile)
            .where(
                SourceFile.knowledge_base_id == kb.id,
                not_deleted(SourceFile),
            )
        )
        if file_count and file_count > 0:
            raise BadRequestError(
                message="知识库已有文档，不能修改 Embedding Model",
                message_key="errors.knowledge.embedding_change_forbidden",
            )
        kb.embedding_model = embedding_model
    changes: dict = {}
    ragflow_fields: dict[str, str] = {}
    if name is not None:
        kb.name = name
        changes["name"] = name
        ragflow_fields["name"] = f"{member.org_id}:{name}"
    if description is not None:
        kb.description = description
        changes["description"] = description
        ragflow_fields["description"] = description
    from app.services import runtime_binding_service

    dataset_id = await runtime_binding_service.get_dataset_id(db, kb)
    if dataset_id and ragflow_fields:
        try:
            await runtime_binding_service.update_dataset_metadata(
                db,
                ragflow,
                kb,
                name=ragflow_fields.get("name"),
                description=ragflow_fields.get("description"),
            )
        except RagflowError as exc:
            raise BadRequestError(message=exc.message, message_key=exc.message_key) from exc
    if changes:
        await write_audit(
            db,
            org_id=member.org_id,
            member_id=member.member_id,
            action=AuditAction.kb_update.value,
            resource_type="knowledge_base",
            resource_id=kb.id,
            details=changes,
        )
    await db.commit()
    await db.refresh(kb)
    return kb


async def delete_knowledge_base(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowRuntimeAdapter,
    kb_id: str,
) -> None:
    kb = await get_knowledge_base(db, member, kb_id)
    if not await has_kb_permission(db, member, kb.id, KbPermission.delete.value) and not await has_kb_permission(
        db, member, kb.id, KbPermission.manage.value
    ):
        raise ForbiddenError()
    kb.status = KnowledgeBaseStatus.deleting.value
    await db.flush()
    try:
        await ragflow.delete_binding(db, kb)
    except RagflowError as exc:
        kb.last_error = exc.message
        await db.commit()
        return
    binding = await runtime_binding_service.get_binding(db, kb.id)
    if binding is not None and binding.deleted_at is None:
        binding.soft_delete()
    kb.soft_delete()
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.kb_delete.value,
        resource_type="knowledge_base",
        resource_id=kb_id,
        details={"name": kb.name},
    )
    await db.commit()


async def list_kb_acl(db: AsyncSession, member: KnowledgePrincipal, kb_id: str) -> list[KnowledgeBaseAcl]:
    await get_knowledge_base(db, member, kb_id)
    if not await has_kb_permission(db, member, kb_id, KbPermission.manage_acl.value) and not await has_kb_permission(
        db, member, kb_id, KbPermission.manage.value
    ):
        if not await has_kb_permission(db, member, kb_id, KbPermission.read.value):
            raise ForbiddenError()
    result = await db.execute(
        select(KnowledgeBaseAcl).where(
            KnowledgeBaseAcl.knowledge_base_id == kb_id,
            not_deleted(KnowledgeBaseAcl),
        )
    )
    return list(result.scalars().all())


async def add_kb_acl(
    db: AsyncSession,
    member: KnowledgePrincipal,
    kb_id: str,
    *,
    subject_type: str,
    subject_id: str,
    permission: str,
    effect: str,
) -> KnowledgeBaseAcl:
    kb = await get_knowledge_base(db, member, kb_id)
    if not await has_kb_permission(db, member, kb_id, KbPermission.manage_acl.value) and not await has_kb_permission(
        db, member, kb_id, KbPermission.manage.value
    ):
        raise ForbiddenError()
    validate_acl_subject(member, subject_type=subject_type, subject_id=subject_id)
    row = KnowledgeBaseAcl(
        knowledge_base_id=kb_id,
        subject_type=subject_type,
        subject_id=subject_id,
        permission=permission,
        effect=effect,
        created_by_member_id=member.member_id,
    )
    db.add(row)
    _bump_kb_acl_version(kb)
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.kb_acl_add.value,
        resource_type="knowledge_base",
        resource_id=kb_id,
        details={
            "subject_type": subject_type,
            "subject_id": subject_id,
            "permission": permission,
            "effect": effect,
            "acl_version": kb.acl_version,
        },
    )
    await db.commit()
    await db.refresh(row)
    return row


async def add_kb_acl_by_role(
    db: AsyncSession,
    member: KnowledgePrincipal,
    kb_id: str,
    *,
    subject_type: str,
    subject_id: str,
    role: str,
    effect: str,
) -> list[KnowledgeBaseAcl]:
    kb = await get_knowledge_base(db, member, kb_id)
    if not await has_kb_permission(db, member, kb_id, KbPermission.manage_acl.value) and not await has_kb_permission(
        db, member, kb_id, KbPermission.manage.value
    ):
        raise ForbiddenError()
    validate_acl_subject(member, subject_type=subject_type, subject_id=subject_id)
    permissions = expand_kb_role_permissions(role)
    rows: list[KnowledgeBaseAcl] = []
    for permission in permissions:
        row = KnowledgeBaseAcl(
            knowledge_base_id=kb_id,
            subject_type=subject_type,
            subject_id=subject_id,
            permission=permission,
            effect=effect,
            created_by_member_id=member.member_id,
        )
        db.add(row)
        rows.append(row)
    _bump_kb_acl_version(kb)
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.kb_acl_add.value,
        resource_type="knowledge_base",
        resource_id=kb_id,
        details={
            "subject_type": subject_type,
            "subject_id": subject_id,
            "role": role,
            "permissions": permissions,
            "effect": effect,
            "acl_version": kb.acl_version,
        },
    )
    await db.commit()
    for row in rows:
        await db.refresh(row)
    return rows


async def delete_kb_acl(db: AsyncSession, member: KnowledgePrincipal, kb_id: str, acl_id: str) -> None:
    kb = await get_knowledge_base(db, member, kb_id)
    if not await has_kb_permission(db, member, kb_id, KbPermission.manage_acl.value) and not await has_kb_permission(
        db, member, kb_id, KbPermission.manage.value
    ):
        raise ForbiddenError()
    acl = await db.get(KnowledgeBaseAcl, acl_id)
    if acl is None or acl.deleted_at is not None or acl.knowledge_base_id != kb_id:
        raise NotFoundError(message="ACL 不存在", message_key="errors.knowledge.acl_not_found")
    acl.soft_delete()
    _bump_kb_acl_version(kb)
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.kb_acl_delete.value,
        resource_type="knowledge_base",
        resource_id=kb_id,
        details={
            "acl_id": acl_id,
            "subject_type": acl.subject_type,
            "subject_id": acl.subject_id,
            "permission": acl.permission,
            "acl_version": kb.acl_version,
        },
    )
    await db.commit()

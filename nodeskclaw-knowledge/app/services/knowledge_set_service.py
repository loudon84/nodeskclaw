"""KnowledgeSet service."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.enums import (
    AclEffect,
    AuditAction,
    KnowledgeSetStatus,
    SetPermission,
)
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_set import KnowledgeSet
from app.models.knowledge_set_acl import KnowledgeSetAcl
from app.models.knowledge_set_item import KnowledgeSetItem
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_base_service
from app.services.permission_service import has_set_permission
from app.services.acl_templates import visibility_acl_specs
from app.services.audit_service import write_audit
from app.services.permission_service import validate_acl_subject


def _bump_set_acl_version(ks: KnowledgeSet) -> None:
    ks.acl_version = (ks.acl_version or 1) + 1


def _seed_visibility_acl(
    db: AsyncSession,
    *,
    knowledge_set_id: str,
    visibility: str,
    member: KnowledgePrincipal,
) -> None:
    specs = visibility_acl_specs(
        visibility,
        org_id=member.org_id,
        department=member.department,
        permissions=[SetPermission.read.value, SetPermission.use.value],
    )
    for subject_type, subject_id, permission in specs:
        db.add(
            KnowledgeSetAcl(
                knowledge_set_id=knowledge_set_id,
                subject_type=subject_type,
                subject_id=subject_id,
                permission=permission,
                effect=AclEffect.allow.value,
                created_by_member_id=member.member_id,
            )
        )


async def list_knowledge_sets(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[KnowledgeSet], int]:
    result = await db.execute(
        select(KnowledgeSet).where(
            KnowledgeSet.org_id == member.org_id,
            not_deleted(KnowledgeSet),
        )
    )
    visible: list[KnowledgeSet] = []
    for row in result.scalars().all():
        if row.owner_member_id == member.member_id:
            visible.append(row)
            continue
        if await has_set_permission(db, member, row, SetPermission.read.value):
            visible.append(row)
            continue
        if await has_set_permission(db, member, row, SetPermission.use.value):
            visible.append(row)
    if q:
        q_lower = q.lower()
        visible = [row for row in visible if q_lower in (row.name or "").lower()]
    sort_attr = sort_by if hasattr(KnowledgeSet, sort_by) else "created_at"
    reverse = sort_order.lower() != "asc"
    visible.sort(key=lambda row: getattr(row, sort_attr) or "", reverse=reverse)
    total = len(visible)
    start = (page - 1) * page_size
    return visible[start : start + page_size], total


async def get_knowledge_set(db: AsyncSession, member: KnowledgePrincipal, set_id: str) -> KnowledgeSet:
    row = await db.get(KnowledgeSet, set_id)
    if row is None or row.deleted_at is not None or row.org_id != member.org_id:
        raise NotFoundError(message="知识集合不存在", message_key="errors.knowledge.set_not_found")
    if not await has_set_permission(db, member, row, SetPermission.read.value):
        raise ForbiddenError()
    return row


async def create_knowledge_set(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    name: str,
    description: str | None,
    embedding_model: str,
    visibility: str,
    retrieval_config: dict[str, Any] | None = None,
) -> KnowledgeSet:
    existing = await db.execute(
        select(KnowledgeSet).where(
            KnowledgeSet.org_id == member.org_id,
            KnowledgeSet.name == name,
            not_deleted(KnowledgeSet),
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(message="知识集合名称已存在", message_key="errors.knowledge.set_name_exists")
    row = KnowledgeSet(
        org_id=member.org_id,
        name=name,
        description=description,
        embedding_model=embedding_model,
        owner_member_id=member.member_id,
        status=KnowledgeSetStatus.active.value,
        visibility=visibility,
    )
    if retrieval_config is not None:
        row.retrieval_config = retrieval_config
    db.add(row)
    await db.flush()
    _seed_visibility_acl(db, knowledge_set_id=row.id, visibility=visibility, member=member)
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.set_create.value,
        resource_type="knowledge_set",
        resource_id=row.id,
        details={"name": name, "visibility": visibility},
    )
    await db.commit()
    await db.refresh(row)
    return row


async def update_knowledge_set(
    db: AsyncSession,
    member: KnowledgePrincipal,
    set_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    status: str | None = None,
    visibility: str | None = None,
    retrieval_config: dict[str, Any] | None = None,
) -> KnowledgeSet:
    row = await get_knowledge_set(db, member, set_id)
    if not await has_set_permission(db, member, row, SetPermission.update.value):
        raise ForbiddenError()
    changes: dict[str, Any] = {}
    if name is not None:
        row.name = name
        changes["name"] = name
    if description is not None:
        row.description = description
        changes["description"] = description
    if status is not None:
        row.status = status
        changes["status"] = status
    if visibility is not None and visibility != row.visibility:
        row.visibility = visibility
        changes["visibility"] = visibility
    if retrieval_config is not None:
        row.retrieval_config = retrieval_config
        changes["retrieval_config"] = retrieval_config
    if changes:
        await write_audit(
            db,
            org_id=member.org_id,
            member_id=member.member_id,
            action=AuditAction.set_update.value,
            resource_type="knowledge_set",
            resource_id=row.id,
            details=changes,
        )
    await db.commit()
    await db.refresh(row)
    return row


async def delete_knowledge_set(db: AsyncSession, member: KnowledgePrincipal, set_id: str) -> None:
    row = await get_knowledge_set(db, member, set_id)
    if not await has_set_permission(db, member, row, SetPermission.delete.value):
        raise ForbiddenError()
    items = await db.execute(
        select(KnowledgeSetItem).where(
            KnowledgeSetItem.knowledge_set_id == set_id,
            not_deleted(KnowledgeSetItem),
        )
    )
    for item in items.scalars().all():
        item.soft_delete()
    row.soft_delete()
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.set_delete.value,
        resource_type="knowledge_set",
        resource_id=set_id,
        details={"name": row.name},
    )
    await db.commit()


async def list_set_items(db: AsyncSession, member: KnowledgePrincipal, set_id: str) -> list[KnowledgeSetItem]:
    await get_knowledge_set(db, member, set_id)
    result = await db.execute(
        select(KnowledgeSetItem).where(
            KnowledgeSetItem.knowledge_set_id == set_id,
            not_deleted(KnowledgeSetItem),
        ).order_by(KnowledgeSetItem.sort_order.asc())
    )
    return list(result.scalars().all())


async def bind_knowledge_base(
    db: AsyncSession,
    member: KnowledgePrincipal,
    set_id: str,
    knowledge_base_id: str,
    *,
    weight: Decimal = Decimal("1.0"),
    sort_order: int = 0,
) -> KnowledgeSetItem:
    ks = await get_knowledge_set(db, member, set_id)
    if not await has_set_permission(db, member, ks, SetPermission.manage.value):
        raise ForbiddenError()
    kb = await knowledge_base_service.get_knowledge_base(db, member, knowledge_base_id)
    if kb.embedding_model != ks.embedding_model:
        raise BadRequestError(
            message="知识库 Embedding Model 与集合不一致",
            message_key="errors.knowledge.embedding_model_mismatch",
        )
    existing = await db.execute(
        select(KnowledgeSetItem).where(
            KnowledgeSetItem.knowledge_set_id == set_id,
            KnowledgeSetItem.knowledge_base_id == knowledge_base_id,
            not_deleted(KnowledgeSetItem),
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(message="知识库已绑定", message_key="errors.knowledge.set_item_exists")
    item = KnowledgeSetItem(
        knowledge_set_id=set_id,
        knowledge_base_id=knowledge_base_id,
        weight=weight,
        sort_order=sort_order,
    )
    db.add(item)
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.set_bind.value,
        resource_type="knowledge_set",
        resource_id=set_id,
        details={"knowledge_base_id": knowledge_base_id, "weight": str(weight), "sort_order": sort_order},
    )
    await db.commit()
    await db.refresh(item)
    return item


async def unbind_knowledge_base(
    db: AsyncSession,
    member: KnowledgePrincipal,
    set_id: str,
    knowledge_base_id: str,
) -> None:
    ks = await get_knowledge_set(db, member, set_id)
    if not await has_set_permission(db, member, ks, SetPermission.manage.value):
        raise ForbiddenError()
    result = await db.execute(
        select(KnowledgeSetItem).where(
            KnowledgeSetItem.knowledge_set_id == set_id,
            KnowledgeSetItem.knowledge_base_id == knowledge_base_id,
            not_deleted(KnowledgeSetItem),
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise NotFoundError(message="绑定不存在", message_key="errors.knowledge.set_item_not_found")
    item.soft_delete()
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.set_unbind.value,
        resource_type="knowledge_set",
        resource_id=set_id,
        details={"knowledge_base_id": knowledge_base_id},
    )
    await db.commit()


async def list_bound_knowledge_bases(
    db: AsyncSession,
    member: KnowledgePrincipal,
    set_id: str,
) -> list[KnowledgeBase]:
    await get_knowledge_set(db, member, set_id)
    items = await list_set_items(db, member, set_id)
    kbs: list[KnowledgeBase] = []
    for item in items:
        kb = await db.get(KnowledgeBase, item.knowledge_base_id)
        if kb and kb.deleted_at is None and kb.org_id == member.org_id:
            kbs.append(kb)
    return kbs


async def list_set_acl(
    db: AsyncSession,
    member: KnowledgePrincipal,
    set_id: str,
) -> list[KnowledgeSetAcl]:
    ks = await get_knowledge_set(db, member, set_id)
    if not await has_set_permission(db, member, ks, SetPermission.manage_acl.value) and not await has_set_permission(
        db, member, ks, SetPermission.manage.value
    ):
        if not await has_set_permission(db, member, ks, SetPermission.read.value):
            raise ForbiddenError()
    result = await db.execute(
        select(KnowledgeSetAcl).where(
            KnowledgeSetAcl.knowledge_set_id == set_id,
            not_deleted(KnowledgeSetAcl),
        )
    )
    return list(result.scalars().all())


async def add_set_acl(
    db: AsyncSession,
    member: KnowledgePrincipal,
    set_id: str,
    *,
    subject_type: str,
    subject_id: str,
    permission: str,
    effect: str,
) -> KnowledgeSetAcl:
    ks = await get_knowledge_set(db, member, set_id)
    if not await has_set_permission(db, member, ks, SetPermission.manage_acl.value) and not await has_set_permission(
        db, member, ks, SetPermission.manage.value
    ):
        raise ForbiddenError()
    validate_acl_subject(member, subject_type=subject_type, subject_id=subject_id)
    row = KnowledgeSetAcl(
        knowledge_set_id=set_id,
        subject_type=subject_type,
        subject_id=subject_id,
        permission=permission,
        effect=effect,
        created_by_member_id=member.member_id,
    )
    db.add(row)
    _bump_set_acl_version(ks)
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.set_acl_change.value,
        resource_type="knowledge_set",
        resource_id=set_id,
        details={
            "operation": "add",
            "subject_type": subject_type,
            "subject_id": subject_id,
            "permission": permission,
            "effect": effect,
            "acl_version": ks.acl_version,
        },
    )
    await db.commit()
    await db.refresh(row)
    return row


async def delete_set_acl(
    db: AsyncSession,
    member: KnowledgePrincipal,
    set_id: str,
    acl_id: str,
) -> None:
    ks = await get_knowledge_set(db, member, set_id)
    if not await has_set_permission(db, member, ks, SetPermission.manage_acl.value) and not await has_set_permission(
        db, member, ks, SetPermission.manage.value
    ):
        raise ForbiddenError()
    acl = await db.get(KnowledgeSetAcl, acl_id)
    if acl is None or acl.deleted_at is not None or acl.knowledge_set_id != set_id:
        raise NotFoundError(message="ACL 不存在", message_key="errors.knowledge.acl_not_found")
    acl.soft_delete()
    _bump_set_acl_version(ks)
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.set_acl_change.value,
        resource_type="knowledge_set",
        resource_id=set_id,
        details={
            "operation": "delete",
            "acl_id": acl_id,
            "subject_type": acl.subject_type,
            "subject_id": acl.subject_id,
            "permission": acl.permission,
            "acl_version": ks.acl_version,
        },
    )
    await db.commit()

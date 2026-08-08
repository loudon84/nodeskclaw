"""KnowledgeSet service."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.enums import KnowledgeSetStatus
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_set import KnowledgeSet
from app.models.knowledge_set_item import KnowledgeSetItem
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_base_service


async def list_knowledge_sets(db: AsyncSession, member: KnowledgePrincipal) -> list[KnowledgeSet]:
    result = await db.execute(
        select(KnowledgeSet).where(
            KnowledgeSet.org_id == member.org_id,
            not_deleted(KnowledgeSet),
        ).order_by(KnowledgeSet.created_at.desc())
    )
    return list(result.scalars().all())


async def get_knowledge_set(db: AsyncSession, member: KnowledgePrincipal, set_id: str) -> KnowledgeSet:
    row = await db.get(KnowledgeSet, set_id)
    if row is None or row.deleted_at is not None or row.org_id != member.org_id:
        raise NotFoundError(message="知识集合不存在", message_key="errors.knowledge.set_not_found")
    return row


async def create_knowledge_set(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    name: str,
    description: str | None,
    embedding_model: str,
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
    )
    db.add(row)
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
) -> KnowledgeSet:
    row = await get_knowledge_set(db, member, set_id)
    if row.owner_member_id != member.member_id and not member.is_super_admin:
        raise ForbiddenError()
    if name is not None:
        row.name = name
    if description is not None:
        row.description = description
    if status is not None:
        row.status = status
    await db.commit()
    await db.refresh(row)
    return row


async def delete_knowledge_set(db: AsyncSession, member: KnowledgePrincipal, set_id: str) -> None:
    row = await get_knowledge_set(db, member, set_id)
    if row.owner_member_id != member.member_id and not member.is_super_admin:
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
    await db.commit()
    await db.refresh(item)
    return item


async def unbind_knowledge_base(
    db: AsyncSession,
    member: KnowledgePrincipal,
    set_id: str,
    knowledge_base_id: str,
) -> None:
    await get_knowledge_set(db, member, set_id)
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

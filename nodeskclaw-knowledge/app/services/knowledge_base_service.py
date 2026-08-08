"""KnowledgeBase CRUD service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.integrations.ragflow.client import RagflowClient
from app.integrations.ragflow.exceptions import RagflowError
from app.models.base import not_deleted
from app.models.enums import AclEffect, KnowledgeBaseStatus, KbPermission, SubjectType
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_base_acl import KnowledgeBaseAcl
from app.schemas.principal import KnowledgePrincipal
from app.services.permission_service import has_kb_permission


async def list_knowledge_bases(db: AsyncSession, member: KnowledgePrincipal) -> list[KnowledgeBase]:
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.org_id == member.org_id,
            not_deleted(KnowledgeBase),
        ).order_by(KnowledgeBase.created_at.desc())
    )
    items = list(result.scalars().all())
    out: list[KnowledgeBase] = []
    for kb in items:
        if await has_kb_permission(db, member, kb.id, KbPermission.read.value):
            out.append(kb)
    return out


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
    ragflow: RagflowClient,
    *,
    name: str,
    description: str | None,
    embedding_model: str,
    chunk_method: str,
    parser_config: dict | None,
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

    try:
        dataset_id = await ragflow.create_dataset(
            name=f"{member.org_id}:{name}",
            embedding_model=embedding_model,
            chunk_method=chunk_method,
            parser_config=parser_config,
            permission="me",
            description=description,
        )
        kb.ragflow_dataset_id = dataset_id
        kb.status = KnowledgeBaseStatus.active.value
    except RagflowError as exc:
        kb.status = KnowledgeBaseStatus.error.value
        await db.commit()
        raise BadRequestError(message=exc.message, message_key=exc.message_key) from exc

    await db.commit()
    await db.refresh(kb)
    return kb


async def update_knowledge_base(
    db: AsyncSession,
    member: KnowledgePrincipal,
    kb_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
) -> KnowledgeBase:
    kb = await get_knowledge_base(db, member, kb_id)
    if not await has_kb_permission(db, member, kb.id, KbPermission.update.value) and not await has_kb_permission(
        db, member, kb.id, KbPermission.manage.value
    ):
        raise ForbiddenError()
    if name is not None:
        kb.name = name
    if description is not None:
        kb.description = description
    await db.commit()
    await db.refresh(kb)
    return kb


async def delete_knowledge_base(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowClient,
    kb_id: str,
) -> None:
    kb = await get_knowledge_base(db, member, kb_id)
    if not await has_kb_permission(db, member, kb.id, KbPermission.delete.value) and not await has_kb_permission(
        db, member, kb.id, KbPermission.manage.value
    ):
        raise ForbiddenError()
    kb.status = KnowledgeBaseStatus.deleting.value
    if kb.ragflow_dataset_id:
        try:
            await ragflow.delete_dataset(kb.ragflow_dataset_id)
        except RagflowError:
            pass
    kb.soft_delete()
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
    await get_knowledge_base(db, member, kb_id)
    if not await has_kb_permission(db, member, kb_id, KbPermission.manage_acl.value) and not await has_kb_permission(
        db, member, kb_id, KbPermission.manage.value
    ):
        raise ForbiddenError()
    row = KnowledgeBaseAcl(
        knowledge_base_id=kb_id,
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


async def delete_kb_acl(db: AsyncSession, member: KnowledgePrincipal, kb_id: str, acl_id: str) -> None:
    await get_knowledge_base(db, member, kb_id)
    if not await has_kb_permission(db, member, kb_id, KbPermission.manage_acl.value) and not await has_kb_permission(
        db, member, kb_id, KbPermission.manage.value
    ):
        raise ForbiddenError()
    acl = await db.get(KnowledgeBaseAcl, acl_id)
    if acl is None or acl.deleted_at is not None or acl.knowledge_base_id != kb_id:
        raise NotFoundError(message="ACL 不存在", message_key="errors.knowledge.acl_not_found")
    acl.soft_delete()
    await db.commit()

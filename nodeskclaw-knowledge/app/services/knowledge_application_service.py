"""KnowledgeApplication service — CRUD, publish, set binding."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.enums import ApplicationPermission, ApplicationStatus, AuditAction
from app.models.knowledge_application import KnowledgeApplication, KnowledgeApplicationSetItem
from app.models.knowledge_application_acl import KnowledgeApplicationAcl
from app.schemas.principal import KnowledgePrincipal
from app.services.audit_service import write_audit
from app.services.permission_service import has_application_permission


async def get_application(
    db: AsyncSession, member: KnowledgePrincipal, application_id: str
) -> KnowledgeApplication:
    app = await db.get(KnowledgeApplication, application_id)
    if app is None or app.deleted_at is not None or app.org_id != member.org_id:
        raise NotFoundError(message="应用不存在", message_key="errors.knowledge.application_not_found")
    return app


async def create_application(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    name: str,
    description: str | None = None,
    answer_model: str | None = None,
    knowledge_set_ids: list[str] | None = None,
) -> KnowledgeApplication:
    if not settings.KNOWLEDGE_V2_APPLICATION_ENABLED:
        raise BadRequestError(
            message="Knowledge Application 未启用",
            message_key="errors.knowledge.application_disabled",
        )
    app = KnowledgeApplication(
        org_id=member.org_id,
        name=name,
        description=description,
        owner_member_id=member.member_id,
        status=ApplicationStatus.draft.value,
        answer_model=answer_model,
    )
    db.add(app)
    await db.flush()
    db.add(
        KnowledgeApplicationAcl(
            application_id=app.id,
            subject_type="member",
            subject_id=member.member_id,
            permission=ApplicationPermission.manage.value,
            effect="allow",
            created_by_member_id=member.member_id,
        )
    )
    for idx, set_id in enumerate(knowledge_set_ids or []):
        db.add(
            KnowledgeApplicationSetItem(
                application_id=app.id,
                knowledge_set_id=set_id,
                sort_order=idx,
            )
        )
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.set_create.value,
        resource_type="knowledge_application",
        resource_id=app.id,
        details={"name": name},
    )
    await db.commit()
    await db.refresh(app)
    return app


async def publish_application(
    db: AsyncSession, member: KnowledgePrincipal, application_id: str
) -> KnowledgeApplication:
    from app.services import application_readiness_service

    app = await get_application(db, member, application_id)
    if not await has_application_permission(db, member, app, ApplicationPermission.manage.value):
        raise ForbiddenError()
    readiness = await application_readiness_service.check(db, member, application_id)
    if not readiness.ready:
        raise ConflictError(
            message="应用未就绪，无法发布",
            message_key="errors.knowledge.application_not_ready",
            details=readiness.to_dict(),
        )
    app.status = ApplicationStatus.active.value
    from app.services import knowledge_quality_service

    app.runtime_snapshot = await knowledge_quality_service.build_runtime_snapshot(db, member, app)
    await db.commit()
    await db.refresh(app)
    return app


async def disable_application(
    db: AsyncSession, member: KnowledgePrincipal, application_id: str
) -> KnowledgeApplication:
    app = await get_application(db, member, application_id)
    if not await has_application_permission(db, member, app, ApplicationPermission.manage.value):
        raise ForbiddenError()
    if app.status != ApplicationStatus.active.value:
        raise BadRequestError(
            message="仅运行中的应用可停用",
            message_key="errors.knowledge.application_not_active",
        )
    app.status = ApplicationStatus.disabled.value
    await db.commit()
    await db.refresh(app)
    return app


async def list_bound_set_ids(db: AsyncSession, application_id: str) -> list[str]:
    rows = await db.scalars(
        select(KnowledgeApplicationSetItem.knowledge_set_id)
        .where(
            KnowledgeApplicationSetItem.application_id == application_id,
            not_deleted(KnowledgeApplicationSetItem),
        )
        .order_by(KnowledgeApplicationSetItem.sort_order.asc())
    )
    return list(rows.all())


async def bind_knowledge_set(
    db: AsyncSession,
    member: KnowledgePrincipal,
    application_id: str,
    knowledge_set_id: str,
    *,
    sort_order: int = 0,
) -> KnowledgeApplicationSetItem:
    app = await get_application(db, member, application_id)
    if not await has_application_permission(db, member, app, ApplicationPermission.manage.value):
        raise ForbiddenError()
    existing = await db.scalar(
        select(KnowledgeApplicationSetItem).where(
            KnowledgeApplicationSetItem.application_id == application_id,
            KnowledgeApplicationSetItem.knowledge_set_id == knowledge_set_id,
            not_deleted(KnowledgeApplicationSetItem),
        )
    )
    if existing is not None:
        return existing
    item = KnowledgeApplicationSetItem(
        application_id=application_id,
        knowledge_set_id=knowledge_set_id,
        sort_order=sort_order,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def list_applications(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[KnowledgeApplication], int]:
    if not settings.KNOWLEDGE_V2_APPLICATION_ENABLED:
        raise BadRequestError(
            message="Knowledge Application 未启用",
            message_key="errors.knowledge.application_disabled",
        )
    result = await db.execute(
        select(KnowledgeApplication).where(
            KnowledgeApplication.org_id == member.org_id,
            not_deleted(KnowledgeApplication),
        )
    )
    rows = list(result.scalars().all())
    visible: list[KnowledgeApplication] = []
    for app in rows:
        if (
            await has_application_permission(db, member, app, ApplicationPermission.use.value)
            or await has_application_permission(db, member, app, ApplicationPermission.manage.value)
            or await has_application_permission(db, member, app, ApplicationPermission.read.value)
        ):
            visible.append(app)
    total = len(visible)
    start = (page - 1) * page_size
    return visible[start : start + page_size], total


async def update_application(
    db: AsyncSession,
    member: KnowledgePrincipal,
    application_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    answer_model: str | None = None,
) -> KnowledgeApplication:
    app = await get_application(db, member, application_id)
    if not await has_application_permission(db, member, app, ApplicationPermission.manage.value):
        raise ForbiddenError()
    if name is not None:
        app.name = name
    if description is not None:
        app.description = description
    if answer_model is not None:
        app.answer_model = answer_model
    await db.commit()
    await db.refresh(app)
    return app


async def unbind_knowledge_set(
    db: AsyncSession,
    member: KnowledgePrincipal,
    application_id: str,
    knowledge_set_id: str,
) -> None:
    app = await get_application(db, member, application_id)
    if not await has_application_permission(db, member, app, ApplicationPermission.manage.value):
        raise ForbiddenError()
    item = await db.scalar(
        select(KnowledgeApplicationSetItem).where(
            KnowledgeApplicationSetItem.application_id == application_id,
            KnowledgeApplicationSetItem.knowledge_set_id == knowledge_set_id,
            not_deleted(KnowledgeApplicationSetItem),
        )
    )
    if item is None:
        raise NotFoundError(message="绑定不存在", message_key="errors.knowledge.application_set_not_bound")
    item.soft_delete()
    await db.commit()


async def application_to_out(db: AsyncSession, app: KnowledgeApplication) -> dict:
    set_ids = await list_bound_set_ids(db, app.id)
    return {
        "id": app.id,
        "org_id": app.org_id,
        "name": app.name,
        "description": app.description,
        "owner_member_id": app.owner_member_id,
        "status": app.status,
        "answer_model": app.answer_model,
        "active_profile_id": app.active_profile_id,
        "acl_version": app.acl_version,
        "visibility": app.visibility,
        "knowledge_set_ids": set_ids,
    }

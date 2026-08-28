"""KnowledgeApplication service — CRUD, publish, set binding, release lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.enums import (
    ApplicationPermission,
    ApplicationReleaseStatus,
    ApplicationStatus,
    AuditAction,
    ReleaseChannelName,
)
from app.models.knowledge_application import KnowledgeApplication, KnowledgeApplicationSetItem
from app.models.knowledge_application_acl import KnowledgeApplicationAcl
from app.models.knowledge_application_release import KnowledgeApplicationRelease, KnowledgeReleaseChannel
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
    db: AsyncSession,
    member: KnowledgePrincipal,
    application_id: str,
    *,
    promote_on_validated: bool = False,
) -> KnowledgeApplication:
    from app.services import application_readiness_service

    app = await get_application(db, member, application_id)
    if not await has_application_permission(db, member, app, ApplicationPermission.manage.value):
        raise ForbiddenError()
    validation_job_id: str | None = None
    if settings.KNOWLEDGE_V24_RELEASE_ENABLED:
        release = await create_release(db, member, application_id)
        release = await validate_release(
            db,
            member,
            application_id,
            release.id,
            promote_on_validated=promote_on_validated,
        )
        validation_job_id = release.validation_job_id
    else:
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
    if validation_job_id is not None:
        app.validation_job_id = validation_job_id
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
    payload = {
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
    validation_job_id = getattr(app, "validation_job_id", None)
    if validation_job_id is not None:
        payload["validation_job_id"] = validation_job_id
    return payload


def _require_release_enabled() -> None:
    if not settings.KNOWLEDGE_V24_RELEASE_ENABLED:
        raise BadRequestError(
            message="Knowledge Release v2.4 未启用",
            message_key="errors.knowledge.release_disabled",
        )


async def ensure_release_channels(
    db: AsyncSession,
    member: KnowledgePrincipal,
    application_id: str,
) -> list[KnowledgeReleaseChannel]:
    app = await get_application(db, member, application_id)
    existing = await db.scalars(
        select(KnowledgeReleaseChannel).where(
            KnowledgeReleaseChannel.application_id == application_id,
            not_deleted(KnowledgeReleaseChannel),
        )
    )
    rows = list(existing.all())
    existing_names = {row.channel for row in rows}
    for channel_name in (ReleaseChannelName.preview.value, ReleaseChannelName.stable.value):
        if channel_name not in existing_names:
            row = KnowledgeReleaseChannel(
                org_id=app.org_id,
                application_id=application_id,
                channel=channel_name,
            )
            db.add(row)
            rows.append(row)
    await db.flush()
    return rows


async def _next_release_version(db: AsyncSession, application_id: str) -> int:
    current = await db.scalar(
        select(func.max(KnowledgeApplicationRelease.version)).where(
            KnowledgeApplicationRelease.application_id == application_id,
            not_deleted(KnowledgeApplicationRelease),
        )
    )
    return int(current or 0) + 1


async def create_release(
    db: AsyncSession,
    member: KnowledgePrincipal,
    application_id: str,
    *,
    retrieval_policy_revision_id: str | None = None,
) -> KnowledgeApplicationRelease:
    _require_release_enabled()
    app = await get_application(db, member, application_id)
    if not await has_application_permission(db, member, app, ApplicationPermission.manage.value):
        raise ForbiddenError()
    from app.models.application_retrieval_policy_revision import ApplicationRetrievalPolicyRevision
    from app.services import application_retrieval_policy_service

    revision: ApplicationRetrievalPolicyRevision | None
    if retrieval_policy_revision_id:
        revision = await db.get(ApplicationRetrievalPolicyRevision, retrieval_policy_revision_id)
    else:
        revision = await application_retrieval_policy_service.get_active_revision(db, application_id)
    if revision is None or revision.deleted_at is not None or revision.application_id != application_id:
        raise BadRequestError(
            message="缺少 Application Retrieval Policy Revision，无法创建 Release",
            message_key="errors.knowledge.retrieval_policy_revision_required",
        )
    from app.services import release_manifest_service
    from app.services.advisory_lock import application_advisory_xact_lock

    await application_advisory_xact_lock(db, application_id)
    version = await _next_release_version(db, application_id)
    manifest = await release_manifest_service.build(
        db,
        member,
        app,
        release_version=version,
        retrieval_policy_revision_id=revision.id,
    )
    release = KnowledgeApplicationRelease(
        org_id=member.org_id,
        application_id=application_id,
        version=version,
        status=ApplicationReleaseStatus.draft.value,
        release_manifest=manifest,
        manifest_hash=release_manifest_service.manifest_hash(manifest),
        created_by_member_id=member.member_id,
    )
    db.add(release)
    await ensure_release_channels(db, member, application_id)
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.set_create.value,
        resource_type="knowledge_application_release",
        resource_id=release.id,
        details={"application_id": application_id, "version": version},
    )
    await db.commit()
    await db.refresh(release)
    return release


async def validate_release(
    db: AsyncSession,
    member: KnowledgePrincipal,
    application_id: str,
    release_id: str,
    *,
    promote_on_validated: bool = False,
) -> KnowledgeApplicationRelease:
    _require_release_enabled()
    app = await get_application(db, member, application_id)
    if not await has_application_permission(db, member, app, ApplicationPermission.manage.value):
        raise ForbiddenError()
    release = await get_release(db, member, application_id, release_id)
    if release.status not in {
        ApplicationReleaseStatus.draft.value,
        ApplicationReleaseStatus.failed.value,
    }:
        raise ConflictError(
            message="Release 状态不允许校验",
            message_key="errors.knowledge.release_validate_invalid_status",
        )
    if not release.release_manifest.get("retrieval_policy_revision_id"):
        raise BadRequestError(
            message="Release Manifest 缺少 retrieval_policy_revision_id",
            message_key="errors.knowledge.retrieval_policy_revision_required",
        )
    release.status = ApplicationReleaseStatus.validating.value
    release.validation_error = None
    await db.flush()
    from app.services import build_orchestrator

    target_key = "promote_stable" if promote_on_validated else "validate_only"
    job = await build_orchestrator.enqueue_build(
        db,
        org_id=member.org_id,
        knowledge_base_id=None,
        index_type="release_validation",
        target_kind="release_validation",
        target_key=target_key,
        release_candidate_id=release.id,
        created_by_member_id=member.member_id,
        trigger_reason="release_validate",
    )
    if job is None:
        raise BadRequestError(
            message="无法创建 Release 校验任务",
            message_key="errors.knowledge.release_validation_enqueue_failed",
        )
    if promote_on_validated and job.target_key != "promote_stable":
        job.target_key = "promote_stable"
    release.validation_job_id = job.id
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.set_update.value,
        resource_type="knowledge_application_release",
        resource_id=release.id,
        details={"application_id": application_id, "action": "validate", "target_key": target_key},
    )
    await db.commit()
    await db.refresh(release)
    return release


async def get_release(
    db: AsyncSession,
    member: KnowledgePrincipal,
    application_id: str,
    release_id: str,
) -> KnowledgeApplicationRelease:
    _require_release_enabled()
    await get_application(db, member, application_id)
    release = await db.get(KnowledgeApplicationRelease, release_id)
    if (
        release is None
        or release.deleted_at is not None
        or release.application_id != application_id
        or release.org_id != member.org_id
    ):
        raise NotFoundError(
            message="Release 不存在",
            message_key="errors.knowledge.release_not_found",
        )
    return release


async def list_releases(
    db: AsyncSession,
    member: KnowledgePrincipal,
    application_id: str,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[KnowledgeApplicationRelease], int]:
    _require_release_enabled()
    await get_application(db, member, application_id)
    result = await db.execute(
        select(KnowledgeApplicationRelease).where(
            KnowledgeApplicationRelease.application_id == application_id,
            not_deleted(KnowledgeApplicationRelease),
        )
    )
    rows = list(result.scalars().all())
    total = len(rows)
    rows.sort(key=lambda row: row.version, reverse=True)
    start = (page - 1) * page_size
    return rows[start : start + page_size], total


async def retire_release(
    db: AsyncSession,
    member: KnowledgePrincipal,
    application_id: str,
    release_id: str,
) -> KnowledgeApplicationRelease:
    _require_release_enabled()
    app = await get_application(db, member, application_id)
    if not await has_application_permission(db, member, app, ApplicationPermission.manage.value):
        raise ForbiddenError()
    release = await get_release(db, member, application_id, release_id)
    if release.status == ApplicationReleaseStatus.retired.value:
        return release
    channels = await db.scalars(
        select(KnowledgeReleaseChannel).where(
            KnowledgeReleaseChannel.application_id == application_id,
            KnowledgeReleaseChannel.active_release_id == release_id,
            not_deleted(KnowledgeReleaseChannel),
        )
    )
    if list(channels.all()):
        raise ConflictError(
            message="Release 仍被 Channel 引用，无法退役",
            message_key="errors.knowledge.release_still_active",
        )
    release.status = ApplicationReleaseStatus.retired.value
    release.retired_at = datetime.now(UTC)
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.set_update.value,
        resource_type="knowledge_application_release",
        resource_id=release.id,
        details={"application_id": application_id, "action": "retire"},
    )
    await db.commit()
    await db.refresh(release)
    return release


async def list_channels(
    db: AsyncSession,
    member: KnowledgePrincipal,
    application_id: str,
) -> list[KnowledgeReleaseChannel]:
    _require_release_enabled()
    await get_application(db, member, application_id)
    return await ensure_release_channels(db, member, application_id)


def release_to_dict(release: KnowledgeApplicationRelease) -> dict:
    return {
        "id": release.id,
        "application_id": release.application_id,
        "version": release.version,
        "status": release.status,
        "release_manifest": release.release_manifest,
        "manifest_hash": release.manifest_hash,
        "quality_snapshot_id": release.quality_snapshot_id,
        "validation_job_id": release.validation_job_id,
        "created_by_member_id": release.created_by_member_id,
        "promoted_at": release.promoted_at.isoformat() if release.promoted_at else None,
        "retired_at": release.retired_at.isoformat() if release.retired_at else None,
        "validation_error": release.validation_error,
        "created_at": release.created_at.isoformat() if release.created_at else None,
    }

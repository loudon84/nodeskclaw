"""API v2 Applications — CRUD and knowledge-set binding."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, get_member_context
from app.core.exceptions import BadRequestError
from app.schemas.common import ApiResponse, PageData
from app.schemas.knowledge import (
    ApplicationRetrievalPolicyRevisionCreate,
    ApplicationRetrievalPolicyRevisionOut,
    KnowledgeApplicationBindSet,
    KnowledgeApplicationCreate,
    KnowledgeApplicationOut,
    KnowledgeApplicationPublish,
    KnowledgeApplicationReleaseCreate,
    KnowledgeApplicationReleaseOut,
    KnowledgeApplicationUpdate,
    KnowledgeReleaseChannelOut,
    KnowledgeReleasePromote,
)
from app.schemas.principal import KnowledgePrincipal
from app.services import (
    application_readiness_service,
    application_retrieval_policy_service,
    knowledge_application_service,
    release_promotion_service,
)

router = APIRouter(tags=["v2-applications"])


def _require_application() -> None:
    if not settings.KNOWLEDGE_API_V2_ENABLED:
        raise BadRequestError(
            message="Knowledge API v2 未启用",
            message_key="errors.knowledge.api_v2_disabled",
        )
    if not settings.KNOWLEDGE_V2_APPLICATION_ENABLED:
        raise BadRequestError(
            message="Knowledge Application 未启用",
            message_key="errors.knowledge.application_disabled",
        )


def _require_release() -> None:
    _require_application()
    if not settings.KNOWLEDGE_V24_RELEASE_ENABLED:
        raise BadRequestError(
            message="Knowledge Release v2.4 未启用",
            message_key="errors.knowledge.release_disabled",
        )


@router.get("/applications", response_model=ApiResponse[PageData[KnowledgeApplicationOut]])
async def list_applications_v2(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_application()
    items, total = await knowledge_application_service.list_applications(
        db, member, page=page, page_size=page_size
    )
    out = [
        KnowledgeApplicationOut.model_validate(
            await knowledge_application_service.application_to_out(db, app)
        )
        for app in items
    ]
    return ApiResponse(data=PageData(items=out, total=total, page=page, page_size=page_size))


@router.post("/applications", response_model=ApiResponse[KnowledgeApplicationOut])
async def create_application_v2(
    body: KnowledgeApplicationCreate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_application()
    app = await knowledge_application_service.create_application(
        db,
        member,
        name=body.name,
        description=body.description,
        answer_model=body.answer_model,
        knowledge_set_ids=body.knowledge_set_ids,
    )
    data = await knowledge_application_service.application_to_out(db, app)
    return ApiResponse(data=KnowledgeApplicationOut.model_validate(data))


@router.get("/applications/{application_id}", response_model=ApiResponse[KnowledgeApplicationOut])
async def get_application_v2(
    application_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_application()
    app = await knowledge_application_service.get_application(db, member, application_id)
    data = await knowledge_application_service.application_to_out(db, app)
    return ApiResponse(data=KnowledgeApplicationOut.model_validate(data))


@router.patch("/applications/{application_id}", response_model=ApiResponse[KnowledgeApplicationOut])
async def patch_application_v2(
    application_id: str,
    body: KnowledgeApplicationUpdate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_application()
    app = await knowledge_application_service.update_application(
        db,
        member,
        application_id,
        name=body.name,
        description=body.description,
        answer_model=body.answer_model,
    )
    data = await knowledge_application_service.application_to_out(db, app)
    return ApiResponse(data=KnowledgeApplicationOut.model_validate(data))


@router.get("/applications/{application_id}/readiness", response_model=ApiResponse)
async def application_readiness_v2(
    application_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_application()
    result = await application_readiness_service.check(db, member, application_id)
    return ApiResponse(data=result.to_dict())


@router.post(
    "/applications/{application_id}/publish",
    response_model=ApiResponse[KnowledgeApplicationOut],
    status_code=status.HTTP_202_ACCEPTED,
)
async def publish_application_v2(
    application_id: str,
    body: KnowledgeApplicationPublish = Body(default_factory=KnowledgeApplicationPublish),
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_application()
    app = await knowledge_application_service.publish_application(
        db,
        member,
        application_id,
        promote_on_validated=body.promote_on_validated,
    )
    data = await knowledge_application_service.application_to_out(db, app)
    return ApiResponse(data=KnowledgeApplicationOut.model_validate(data))


@router.post("/applications/{application_id}/disable", response_model=ApiResponse[KnowledgeApplicationOut])
async def disable_application_v2(
    application_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_application()
    app = await knowledge_application_service.disable_application(db, member, application_id)
    data = await knowledge_application_service.application_to_out(db, app)
    return ApiResponse(data=KnowledgeApplicationOut.model_validate(data))


@router.post("/applications/{application_id}/knowledge-sets", response_model=ApiResponse)
async def bind_application_set_v2(
    application_id: str,
    body: KnowledgeApplicationBindSet,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_application()
    item = await knowledge_application_service.bind_knowledge_set(
        db,
        member,
        application_id,
        body.knowledge_set_id,
        sort_order=body.sort_order,
    )
    return ApiResponse(
        data={"id": item.id, "knowledge_set_id": item.knowledge_set_id, "sort_order": item.sort_order}
    )


@router.delete(
    "/applications/{application_id}/knowledge-sets/{knowledge_set_id}",
    response_model=ApiResponse,
)
async def unbind_application_set_v2(
    application_id: str,
    knowledge_set_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_application()
    await knowledge_application_service.unbind_knowledge_set(
        db, member, application_id, knowledge_set_id
    )
    return ApiResponse(message="deleted")


@router.get(
    "/applications/{application_id}/releases",
    response_model=ApiResponse[PageData[KnowledgeApplicationReleaseOut]],
)
async def list_application_releases_v2(
    application_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_release()
    items, total = await knowledge_application_service.list_releases(
        db, member, application_id, page=page, page_size=page_size
    )
    out = [
        KnowledgeApplicationReleaseOut.model_validate(knowledge_application_service.release_to_dict(item))
        for item in items
    ]
    return ApiResponse(data=PageData(items=out, total=total, page=page, page_size=page_size))


@router.post(
    "/applications/{application_id}/releases",
    response_model=ApiResponse[KnowledgeApplicationReleaseOut],
)
async def create_application_release_v2(
    application_id: str,
    body: KnowledgeApplicationReleaseCreate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_release()
    release = await knowledge_application_service.create_release(
        db,
        member,
        application_id,
        retrieval_policy_revision_id=body.retrieval_policy_revision_id,
    )
    return ApiResponse(
        data=KnowledgeApplicationReleaseOut.model_validate(
            knowledge_application_service.release_to_dict(release)
        )
    )


@router.get(
    "/applications/{application_id}/releases/{release_id}",
    response_model=ApiResponse[KnowledgeApplicationReleaseOut],
)
async def get_application_release_v2(
    application_id: str,
    release_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_release()
    release = await knowledge_application_service.get_release(db, member, application_id, release_id)
    return ApiResponse(
        data=KnowledgeApplicationReleaseOut.model_validate(
            knowledge_application_service.release_to_dict(release)
        )
    )


@router.post(
    "/applications/{application_id}/releases/{release_id}/validate",
    response_model=ApiResponse[KnowledgeApplicationReleaseOut],
    status_code=status.HTTP_202_ACCEPTED,
)
async def validate_application_release_v2(
    application_id: str,
    release_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_release()
    release = await knowledge_application_service.validate_release(
        db, member, application_id, release_id
    )
    return ApiResponse(
        data=KnowledgeApplicationReleaseOut.model_validate(
            knowledge_application_service.release_to_dict(release)
        )
    )


@router.post(
    "/applications/{application_id}/releases/{release_id}/retire",
    response_model=ApiResponse[KnowledgeApplicationReleaseOut],
)
async def retire_application_release_v2(
    application_id: str,
    release_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_release()
    release = await knowledge_application_service.retire_release(
        db, member, application_id, release_id
    )
    return ApiResponse(
        data=KnowledgeApplicationReleaseOut.model_validate(
            knowledge_application_service.release_to_dict(release)
        )
    )


@router.get(
    "/applications/{application_id}/channels",
    response_model=ApiResponse[list[KnowledgeReleaseChannelOut]],
)
async def list_application_channels_v2(
    application_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_release()
    channels = await knowledge_application_service.list_channels(db, member, application_id)
    return ApiResponse(
        data=[
            KnowledgeReleaseChannelOut.model_validate(release_promotion_service.channel_to_dict(row))
            for row in channels
        ]
    )


@router.post(
    "/applications/{application_id}/channels/{channel}/promote",
    response_model=ApiResponse[KnowledgeReleaseChannelOut],
)
async def promote_application_channel_v2(
    application_id: str,
    channel: str,
    body: KnowledgeReleasePromote,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_release()
    row = await release_promotion_service.promote(
        db,
        member,
        application_id,
        channel=channel,
        release_id=body.release_id,
    )
    return ApiResponse(data=KnowledgeReleaseChannelOut.model_validate(release_promotion_service.channel_to_dict(row)))


@router.post(
    "/applications/{application_id}/channels/{channel}/rollback",
    response_model=ApiResponse[KnowledgeReleaseChannelOut],
)
async def rollback_application_channel_v2(
    application_id: str,
    channel: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_release()
    row = await release_promotion_service.rollback(db, member, application_id, channel=channel)
    return ApiResponse(data=KnowledgeReleaseChannelOut.model_validate(release_promotion_service.channel_to_dict(row)))


@router.get(
    "/applications/{application_id}/retrieval-policy-revisions",
    response_model=ApiResponse[list[ApplicationRetrievalPolicyRevisionOut]],
)
async def list_application_retrieval_policy_revisions_v2(
    application_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_release()
    rows = await application_retrieval_policy_service.list_revisions(db, member, application_id)
    return ApiResponse(
        data=[
            ApplicationRetrievalPolicyRevisionOut.model_validate(
                application_retrieval_policy_service.revision_to_dict(row)
            )
            for row in rows
        ]
    )


@router.post(
    "/applications/{application_id}/retrieval-policy-revisions",
    response_model=ApiResponse[ApplicationRetrievalPolicyRevisionOut],
)
async def create_application_retrieval_policy_revision_v2(
    application_id: str,
    body: ApplicationRetrievalPolicyRevisionCreate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_release()
    revision = await application_retrieval_policy_service.create_revision(
        db,
        member,
        application_id,
        query_intelligence_policy=body.query_intelligence_policy,
        provider_policy=body.provider_policy,
        provider_weights=body.provider_weights,
        candidate_budget=body.candidate_budget,
        fanout_budget=body.fanout_budget,
        latency_budget=body.latency_budget,
        fallback_policy=body.fallback_policy,
        artifact_policy=body.artifact_policy,
        fusion_policy=body.fusion_policy,
        notes=body.notes,
    )
    return ApiResponse(
        data=ApplicationRetrievalPolicyRevisionOut.model_validate(
            application_retrieval_policy_service.revision_to_dict(revision)
        )
    )


@router.post(
    "/applications/{application_id}/retrieval-policy-revisions/{revision_id}/publish",
    response_model=ApiResponse[ApplicationRetrievalPolicyRevisionOut],
)
async def publish_application_retrieval_policy_revision_v2(
    application_id: str,
    revision_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_release()
    revision = await application_retrieval_policy_service.publish_revision(
        db, member, application_id, revision_id
    )
    return ApiResponse(
        data=ApplicationRetrievalPolicyRevisionOut.model_validate(
            application_retrieval_policy_service.revision_to_dict(revision)
        )
    )

"""API v2 Quality routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, get_member_context
from app.core.exceptions import BadRequestError
from app.schemas.common import ApiResponse
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_quality_service

router = APIRouter(tags=["v2-quality"])


def _require_quality_api() -> None:
    if not settings.KNOWLEDGE_API_V2_ENABLED:
        raise BadRequestError(
            message="Knowledge API v2 未启用",
            message_key="errors.knowledge.api_v2_disabled",
        )


@router.get("/knowledge-bases/{kb_id}/quality")
async def get_kb_quality(
    kb_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_quality_api()
    return ApiResponse(data=await knowledge_quality_service.get_kb_quality(db, member, kb_id))


@router.get("/applications/{application_id}/quality")
async def get_application_quality(
    application_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_quality_api()
    return ApiResponse(data=await knowledge_quality_service.get_application_quality(db, member, application_id))


@router.get("/knowledge-bases/{kb_id}/quality/history")
async def get_kb_quality_history(
    kb_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_quality_api()
    if settings.KNOWLEDGE_V24_RELEASE_ENABLED:
        history = await knowledge_quality_service.get_quality_history(
            db,
            member,
            scope_type="knowledge_base",
            scope_id=kb_id,
        )
    else:
        current = await knowledge_quality_service.get_kb_quality(db, member, kb_id)
        history = [current] if settings.KNOWLEDGE_V23_QUALITY_ENABLED else []
    return ApiResponse(data={"history": history})

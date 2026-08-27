"""API v2 Knowledge Model revision routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, get_member_context
from app.core.exceptions import BadRequestError
from app.schemas.common import ApiResponse
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_model_service

router = APIRouter(tags=["v2-knowledge-models"])


def _require_model_revision_api() -> None:
    if not settings.KNOWLEDGE_API_V2_ENABLED:
        raise BadRequestError(
            message="Knowledge API v2 未启用",
            message_key="errors.knowledge.api_v2_disabled",
        )


@router.get("/knowledge-models/{model_id}/revisions")
async def list_model_revisions(
    model_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_model_revision_api()
    rows = await knowledge_model_service.list_revisions(db, member, model_id)
    return ApiResponse(
        data=[
            {
                "id": row.id,
                "revision_number": row.revision_number,
                "status": row.status,
                "content_hash": row.content_hash,
                "published_at": row.published_at.isoformat() if row.published_at else None,
            }
            for row in rows
        ]
    )


@router.get("/knowledge-models/{model_id}/revisions/{revision_id}")
async def get_model_revision(
    model_id: str,
    revision_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_model_revision_api()
    row = await knowledge_model_service.get_revision(db, member, model_id, revision_id)
    return ApiResponse(
        data={
            "id": row.id,
            "revision_number": row.revision_number,
            "status": row.status,
            "content_hash": row.content_hash,
            "entities": row.entities,
            "relations": row.relations,
            "terms": row.terms,
            "extraction_policy": row.extraction_policy,
            "published_at": row.published_at.isoformat() if row.published_at else None,
        }
    )


@router.post("/knowledge-models/{model_id}/revisions/{revision_id}/publish")
async def publish_model_revision(
    model_id: str,
    revision_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_model_revision_api()
    if not settings.KNOWLEDGE_V23_MODEL_REVISION_ENABLED:
        raise BadRequestError(
            message="Knowledge Model Revision 未启用",
            message_key="errors.knowledge.model_revision_disabled",
        )
    row = await knowledge_model_service.publish_revision(db, member, model_id, revision_id)
    active = await knowledge_model_service.get_active_revision(db, row)
    return ApiResponse(data=knowledge_model_service.model_to_dict(row, revision=active))

"""Query intelligence debug API — playground/manage only."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, get_member_context
from app.core.exceptions import BadRequestError
from app.schemas.common import ApiResponse
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_model_service
from app.services.query_intelligence import analyze_query

router = APIRouter(tags=["v2-query-intelligence"])


class QueryIntelligenceRequest(BaseModel):
    query: str = Field(min_length=1)
    knowledge_model_id: str | None = None
    access_scope: str = "full"
    profile_policy: dict | None = None


def _require_query_intelligence_api() -> None:
    if not settings.KNOWLEDGE_API_V2_ENABLED:
        raise BadRequestError(
            message="Knowledge API v2 未启用",
            message_key="errors.knowledge.api_v2_disabled",
        )


@router.post("/query-intelligence/analyze")
async def analyze_query_intelligence(
    body: QueryIntelligenceRequest,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_query_intelligence_api()
    terms = None
    if body.knowledge_model_id:
        model = await knowledge_model_service.get_model(db, member, body.knowledge_model_id)
        active = await knowledge_model_service.get_active_revision(db, model)
        terms = (active.terms if active else model.terms) or []
    analysis = await analyze_query(
        body.query,
        terms=terms,
        access_scope=body.access_scope,
        profile_policy=body.profile_policy,
    )
    return ApiResponse(data={"query_analysis": analysis.to_dict()})

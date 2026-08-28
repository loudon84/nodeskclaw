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
from app.services.query_intelligence import analyze_query, resolve_release_terms

router = APIRouter(tags=["v2-query-intelligence"])


class QueryIntelligenceRequest(BaseModel):
    query: str = Field(min_length=1)
    knowledge_model_id: str | None = None
    access_scope: str = "full"
    profile_policy: dict | None = None
    manifest: dict | None = None
    kb_access_scopes: dict[str, str] | None = None


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
    model_revision_ids: list[str] = []
    if body.manifest:
        for ks in body.manifest.get("knowledge_sets") or []:
            if not isinstance(ks, dict):
                continue
            for kb_pin in ks.get("knowledge_bases") or []:
                if not isinstance(kb_pin, dict):
                    continue
                revision_id = kb_pin.get("knowledge_model_revision_id")
                if revision_id and str(revision_id) not in model_revision_ids:
                    model_revision_ids.append(str(revision_id))
    release_terms, term_diagnostics = await resolve_release_terms(
        db,
        knowledge_model_revision_ids=model_revision_ids,
        query=body.query,
        kb_terms={},
    )
    merged_terms = list(dict.fromkeys((terms or []) + release_terms)) if (terms or release_terms) else None
    analysis = await analyze_query(
        body.query,
        terms=merged_terms,
        access_scope=body.access_scope,
        profile_policy=body.profile_policy,
    )
    if term_diagnostics:
        analysis.reason_codes.extend(term_diagnostics)

    data: dict = {"query_analysis": analysis.to_dict()}
    if settings.KNOWLEDGE_V24_FEDERATION_ENABLED:
        from app.services.federated_retrieval_planner import build_federation_plan

        federation_plan = build_federation_plan(
            body.query,
            manifest=body.manifest,
            query_analysis=analysis,
            kb_access_scopes=body.kb_access_scopes or {},
            profile_policy=body.profile_policy,
        )
        data["federation_plan"] = federation_plan.to_dict()
    return ApiResponse(data=data)

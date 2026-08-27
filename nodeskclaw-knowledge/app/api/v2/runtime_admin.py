"""API v2 Runtime Admin — super-admin runtime health and capability probes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, get_member_context
from app.core.exceptions import BadRequestError, ForbiddenError
from app.runtime.ragflow import RagflowRuntimeAdapter
from app.schemas.common import ApiResponse
from app.schemas.principal import KnowledgePrincipal
from app.services import runtime_binding_service

router = APIRouter(prefix="/runtime", tags=["v2-runtime-admin"])


def _require_super_admin(member: KnowledgePrincipal) -> None:
    if not settings.KNOWLEDGE_API_V2_ENABLED:
        raise BadRequestError(
            message="Knowledge API v2 未启用",
            message_key="errors.knowledge.api_v2_disabled",
        )
    if not member.is_super_admin:
        raise ForbiddenError(
            message="需要超级管理员权限",
            message_key="errors.knowledge.super_admin_required",
        )


@router.get("/health")
async def runtime_health(
    member: KnowledgePrincipal = Depends(get_member_context),
):
    _require_super_admin(member)
    adapter = RagflowRuntimeAdapter()
    try:
        health = await adapter.check_health()
        return ApiResponse(
            data={
                "reachable": health.reachable,
                "version": health.version,
                "chunk_retrieval_ok": health.chunk_retrieval_ok,
                "degraded_reasons": health.degraded_reasons,
            }
        )
    finally:
        await adapter.aclose()


@router.get("/capabilities")
async def runtime_capabilities(
    member: KnowledgePrincipal = Depends(get_member_context),
):
    _require_super_admin(member)
    adapter = RagflowRuntimeAdapter()
    try:
        caps = await adapter.probe_capabilities()
        version = adapter._last_probe_version
        return ApiResponse(
            data={
                "reachable": adapter._last_probe_reachable,
                "runtime_version": version,
                "capabilities": caps,
            }
        )
    finally:
        await adapter.aclose()


@router.post("/capabilities/probe")
async def runtime_capabilities_probe(
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_super_admin(member)
    adapter = RagflowRuntimeAdapter()
    try:
        stats = await runtime_binding_service.probe_all_bindings(db, adapter)
        caps = await adapter.probe_capabilities()
        return ApiResponse(
            data={
                "bindings_probed": stats.get("probed", 0),
                "bindings_failed": stats.get("failed", 0),
                "runtime_version": adapter._last_probe_version,
                "capabilities": caps,
            }
        )
    finally:
        await adapter.aclose()

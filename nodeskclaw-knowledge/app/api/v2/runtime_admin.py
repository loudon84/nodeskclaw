"""API v2 Runtime Admin — super-admin runtime health and capability probes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, get_member_context, get_runtime_adapter
from app.core.exceptions import BadRequestError, ForbiddenError
from app.runtime.ragflow import RagflowRuntimeAdapter
from app.schemas.common import ApiResponse
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_base_service, metrics_service, reconciliation_service, runtime_binding_service

router = APIRouter(prefix="/runtime", tags=["v2-runtime-admin"])
kb_runtime_router = APIRouter(tags=["v2-runtime-admin"])


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


@router.get("/workers")
async def runtime_workers(
    member: KnowledgePrincipal = Depends(get_member_context),
):
    _require_super_admin(member)
    heartbeats = metrics_service.worker_heartbeat_snapshot()
    return ApiResponse(
        data={
            "workers": [
                {
                    "role": role,
                    "last_heartbeat_at": heartbeats.get(role),
                }
                for role in ("ingestion", "build", "maintenance", "connector", "translation")
            ]
        }
    )


@kb_runtime_router.get("/knowledge-bases/{kb_id}/runtime")
async def kb_runtime_diagnostics(
    kb_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_super_admin(member)
    kb = await knowledge_base_service.get_knowledge_base(db, member, kb_id)
    binding = await runtime_binding_service.get_binding(db, kb.id)
    data = reconciliation_service.build_runtime_diagnostics(binding)
    data["knowledge_base_id"] = kb.id
    data["knowledge_base_status"] = kb.status
    return ApiResponse(data=data)


class RuntimeReconcileRequest(BaseModel):
    repair_mode: str | None = Field(default=None, description="显式 reprovision 才重建缺失 Dataset")


@kb_runtime_router.post("/knowledge-bases/{kb_id}/runtime/reconcile")
async def kb_runtime_reconcile(
    kb_id: str,
    body: RuntimeReconcileRequest | None = None,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowRuntimeAdapter = Depends(get_runtime_adapter),
):
    _require_super_admin(member)
    await knowledge_base_service.get_knowledge_base(db, member, kb_id)
    repair_mode = body.repair_mode if body else None
    if repair_mode is not None and repair_mode not in {None, "reprovision"}:
        raise BadRequestError(
            message="不支持的 repair_mode",
            message_key="errors.knowledge.repair_mode_invalid",
        )
    result = await reconciliation_service.reconcile_knowledge_base_runtime(
        db,
        ragflow,
        kb_id,
        repair_mode=repair_mode,
    )
    await db.commit()
    return ApiResponse(data=result)

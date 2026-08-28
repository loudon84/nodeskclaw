"""API v2 Engineering — index state, build profiles, build jobs."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, get_member_context
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.build_job import KnowledgeBuildJob
from app.models.enums import BuildJobStatus, IndexStateStatus, IndexType, KbPermission
from app.schemas.common import ApiResponse, PageData
from app.schemas.principal import KnowledgePrincipal
from app.services import (
    build_orchestrator,
    build_profile_service,
    index_state_service,
    knowledge_base_service,
    permission_service,
    runtime_binding_service,
)

router = APIRouter(tags=["v2-engineering"])


def _require_api_v2() -> None:
    if not settings.KNOWLEDGE_API_V2_ENABLED:
        raise BadRequestError(
            message="Knowledge API v2 未启用",
            message_key="errors.knowledge.api_v2_disabled",
        )


def _require_build_enabled() -> None:
    _require_api_v2()
    if not settings.KNOWLEDGE_V2_BUILD_ENABLED:
        raise BadRequestError(
            message="Knowledge Build 未启用",
            message_key="errors.knowledge.build_disabled",
        )


def _profile_out(profile) -> dict:
    return {
        "id": profile.id,
        "name": profile.name,
        "description": profile.description,
        "system_key": profile.system_key,
        "is_system": profile.is_system,
        "index_types": profile.index_types,
        "artifact_types": getattr(profile, "artifact_types", None) or [],
        "trigger_policy": profile.trigger_policy,
        "artifact_trigger_policy": getattr(profile, "artifact_trigger_policy", None) or {},
        "version": profile.version,
    }


def _build_job_out(job: KnowledgeBuildJob) -> dict:
    return {
        "id": job.id,
        "org_id": job.org_id,
        "knowledge_base_id": job.knowledge_base_id,
        "build_profile_id": job.build_profile_id,
        "index_type": job.index_type,
        "trigger_reason": job.trigger_reason,
        "status": job.status,
        "progress": job.progress,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "attempt_count": job.attempt_count,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


def _index_state_out(state, *, capabilities: dict | None = None) -> dict:
    payload: dict = {
        "build_status": state.status,
        "retrieval_status": state.retrieval_status,
    }
    if state.last_error:
        payload["last_error"] = state.last_error
    caps = capabilities or {}
    runtime_feature = caps.get("index_types") or caps.get("supported_indexes")
    if runtime_feature is not None:
        payload["runtime_feature"] = runtime_feature
    if state.validation_payload is not None:
        payload["validation"] = state.validation_payload
    if state.coverage_payload is not None:
        payload["coverage"] = state.coverage_payload
    if state.last_validated_at is not None:
        payload["last_validated_at"] = state.last_validated_at.isoformat()
    return payload


async def _require_kb_manage(db: AsyncSession, member: KnowledgePrincipal, kb_id: str):
    kb = await knowledge_base_service.get_knowledge_base(db, member, kb_id)
    if not await permission_service.has_kb_permission(db, member, kb.id, KbPermission.manage.value):
        raise ForbiddenError()
    return kb


class BuildProfileUpdate(BaseModel):
    build_profile_id: str = Field(min_length=1)


class TriggerBuildsRequest(BaseModel):
    index_types: list[str] = Field(min_length=1)
    force: bool = False


@router.get("/knowledge-bases/{kb_id}/indexes")
async def list_kb_indexes(
    kb_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_api_v2()
    kb = await knowledge_base_service.get_knowledge_base(db, member, kb_id)
    binding = await runtime_binding_service.get_binding(db, kb.id)
    capabilities = (binding.capabilities if binding else None) or {}
    states = await index_state_service.ensure_kb_index_states(
        db,
        org_id=member.org_id,
        kb=kb,
        capabilities=capabilities,
    )
    return ApiResponse(
        data={
            state.index_type: _index_state_out(state, capabilities=capabilities)
            for state in states
        }
    )


@router.get("/knowledge-bases/{kb_id}/build-profile")
async def get_kb_build_profile(
    kb_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_api_v2()
    kb = await knowledge_base_service.get_knowledge_base(db, member, kb_id)
    profile = await build_profile_service.resolve_profile_for_kb(db, kb)
    return ApiResponse(
        data={
            "active_build_profile_id": kb.active_build_profile_id,
            "resolved_profile": _profile_out(profile),
        }
    )


@router.put("/knowledge-bases/{kb_id}/build-profile")
async def put_kb_build_profile(
    kb_id: str,
    body: BuildProfileUpdate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_build_enabled()
    kb = await _require_kb_manage(db, member, kb_id)
    profile = await build_profile_service.get_profile(db, body.build_profile_id)
    if profile is None:
        raise NotFoundError(
            message="Build Profile 不存在",
            message_key="errors.knowledge.build_profile_not_found",
        )
    if profile.org_id is not None and profile.org_id != member.org_id:
        raise ForbiddenError()
    kb.active_build_profile_id = profile.id
    await db.flush()
    return ApiResponse(
        data={
            "active_build_profile_id": kb.active_build_profile_id,
            "resolved_profile": _profile_out(profile),
        }
    )


@router.post("/knowledge-bases/{kb_id}/builds")
async def trigger_kb_builds(
    kb_id: str,
    body: TriggerBuildsRequest,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_build_enabled()
    kb = await _require_kb_manage(db, member, kb_id)
    profile = await build_profile_service.resolve_profile_for_kb(db, kb)
    binding = await runtime_binding_service.get_binding(db, kb.id)
    capabilities = (binding.capabilities if binding else None) or {}
    await index_state_service.ensure_kb_index_states(
        db,
        org_id=member.org_id,
        kb=kb,
        capabilities=capabilities,
    )
    jobs: list[KnowledgeBuildJob] = []
    for index_type in body.index_types:
        if index_type == IndexType.chunk.value:
            continue
        if body.force:
            state = await index_state_service.get_or_create_state(
                db,
                org_id=member.org_id,
                knowledge_base_id=kb.id,
                index_type=index_type,
            )
            if state.status in {
                IndexStateStatus.ready.value,
                IndexStateStatus.failed.value,
                IndexStateStatus.stale.value,
            }:
                state.status = IndexStateStatus.stale.value
        job = await build_orchestrator.enqueue_build(
            db,
            org_id=member.org_id,
            knowledge_base_id=kb.id,
            index_type=index_type,
            trigger_reason="manual_api",
            build_profile_id=profile.id,
            created_by_member_id=member.member_id,
        )
        if job is not None:
            jobs.append(job)
    return ApiResponse(data={"jobs": [_build_job_out(job) for job in jobs]})


@router.get("/builds")
async def list_builds(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    knowledge_base_id: str | None = None,
    status: str | None = None,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_build_enabled()
    stmt = select(KnowledgeBuildJob).where(
        KnowledgeBuildJob.org_id == member.org_id,
        not_deleted(KnowledgeBuildJob),
    )
    if knowledge_base_id:
        stmt = stmt.where(KnowledgeBuildJob.knowledge_base_id == knowledge_base_id)
    if status:
        stmt = stmt.where(KnowledgeBuildJob.status == status)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int(await db.scalar(count_stmt) or 0)
    stmt = (
        stmt.order_by(KnowledgeBuildJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = await db.scalars(stmt)
    items = [_build_job_out(job) for job in rows.all()]
    return ApiResponse(data=PageData(items=items, total=total, page=page, page_size=page_size))


@router.get("/builds/{build_id}")
async def get_build(
    build_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_build_enabled()
    job = await db.get(KnowledgeBuildJob, build_id)
    if job is None or job.deleted_at is not None or job.org_id != member.org_id:
        raise NotFoundError(
            message="Build Job 不存在",
            message_key="errors.knowledge.build_job_not_found",
        )
    if not await permission_service.has_kb_permission(
        db, member, job.knowledge_base_id, KbPermission.read.value
    ):
        raise ForbiddenError()
    return ApiResponse(data=_build_job_out(job))


@router.post("/builds/{build_id}/retry")
async def retry_build(
    build_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_build_enabled()
    job = await db.get(KnowledgeBuildJob, build_id)
    if job is None or job.deleted_at is not None or job.org_id != member.org_id:
        raise NotFoundError(
            message="Build Job 不存在",
            message_key="errors.knowledge.build_job_not_found",
        )
    if not await permission_service.has_kb_permission(
        db, member, job.knowledge_base_id, KbPermission.manage.value
    ):
        raise ForbiddenError()
    if job.status not in {BuildJobStatus.failed.value, BuildJobStatus.cancelled.value}:
        raise BadRequestError(
            message="仅 failed 或 cancelled 状态的 Build Job 可重试",
            message_key="errors.knowledge.build_job_not_retryable",
        )
    job.status = BuildJobStatus.queued.value
    job.next_run_at = datetime.now(UTC)
    job.finished_at = None
    job.error_code = None
    job.error_message = None
    job.progress = 0
    await db.flush()
    return ApiResponse(data=_build_job_out(job))

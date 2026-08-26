"""Build orchestrator — enqueue and process KnowledgeBuildJob (not IngestionJob)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.base import not_deleted
from app.models.build_job import KnowledgeBuildJob
from app.models.enums import BuildJobStatus, BuildTriggerPolicy, IndexStateStatus, IndexType
from app.services import build_profile_service, index_state_service
from app.services.index_registry import get_descriptor, is_runtime_supported
from app.workers.job_leasing import claim_next, clear_lease_if_owner

logger = logging.getLogger(__name__)

LEASE_SECONDS = settings.KNOWLEDGE_BUILD_LEASE_SECONDS


async def enqueue_build(
    db: AsyncSession,
    *,
    org_id: str,
    knowledge_base_id: str,
    index_type: str,
    trigger_reason: str,
    build_profile_id: str | None = None,
    created_by_member_id: str | None = None,
    delay_seconds: int = 0,
) -> KnowledgeBuildJob | None:
    if index_type == IndexType.chunk.value:
        return None
    existing = await db.scalar(
        select(KnowledgeBuildJob).where(
            KnowledgeBuildJob.knowledge_base_id == knowledge_base_id,
            KnowledgeBuildJob.index_type == index_type,
            KnowledgeBuildJob.status.in_(
                [BuildJobStatus.queued.value, BuildJobStatus.running.value]
            ),
            not_deleted(KnowledgeBuildJob),
        )
    )
    if existing is not None:
        if delay_seconds > 0 and existing.status == BuildJobStatus.queued.value:
            desired = datetime.now(UTC) + timedelta(seconds=delay_seconds)
            if existing.next_run_at is None or existing.next_run_at < desired:
                existing.next_run_at = desired
        return existing
    next_run = None
    if delay_seconds > 0:
        next_run = datetime.now(UTC) + timedelta(seconds=delay_seconds)
    job = KnowledgeBuildJob(
        org_id=org_id,
        knowledge_base_id=knowledge_base_id,
        build_profile_id=build_profile_id,
        index_type=index_type,
        trigger_reason=trigger_reason,
        status=BuildJobStatus.queued.value,
        next_run_at=next_run,
        created_by_member_id=created_by_member_id,
    )
    db.add(job)
    await db.flush()
    return job


async def enqueue_after_activation(
    db: AsyncSession,
    *,
    org_id: str,
    kb,
    source_file_id: str,
    version_id: str,
    capabilities: dict | None = None,
    member_id: str | None = None,
) -> list[KnowledgeBuildJob]:
    if not settings.KNOWLEDGE_V2_BUILD_ENABLED:
        await index_state_service.mark_indexes_stale(
            db,
            org_id=org_id,
            kb=kb,
            source_watermark=version_id,
            capabilities=capabilities,
        )
        return []

    profile = await build_profile_service.resolve_profile_for_kb(db, kb)
    await index_state_service.ensure_kb_index_states(
        db, org_id=org_id, kb=kb, capabilities=capabilities
    )
    await index_state_service.mark_indexes_stale(
        db,
        org_id=org_id,
        kb=kb,
        index_types=list(profile.index_types or []),
        source_watermark=version_id,
        capabilities=capabilities,
    )

    policy_map = profile.trigger_policy or {}
    enqueued: list[KnowledgeBuildJob] = []
    for index_type in profile.index_types or []:
        if index_type == IndexType.chunk.value:
            continue
        if not is_runtime_supported(index_type, capabilities):
            state = await index_state_service.get_or_create_state(
                db,
                org_id=org_id,
                knowledge_base_id=kb.id,
                index_type=index_type,
            )
            state.status = IndexStateStatus.unsupported.value
            state.last_error = "runtime_public_api_unavailable"
            continue
        policy = policy_map.get(index_type) or (get_descriptor(index_type) or {}).get(
            "trigger_policy"
        )
        if policy == BuildTriggerPolicy.manual.value:
            continue
        if policy == BuildTriggerPolicy.debounce.value:
            delay = int((get_descriptor(index_type) or {}).get("debounce_seconds") or 300)
            job = await enqueue_build(
                db,
                org_id=org_id,
                knowledge_base_id=kb.id,
                index_type=index_type,
                trigger_reason="activate_debounce",
                build_profile_id=profile.id,
                created_by_member_id=member_id,
                delay_seconds=delay,
            )
        elif policy == BuildTriggerPolicy.on_activate.value:
            job = await enqueue_build(
                db,
                org_id=org_id,
                knowledge_base_id=kb.id,
                index_type=index_type,
                trigger_reason="activate",
                build_profile_id=profile.id,
                created_by_member_id=member_id,
            )
        else:
            continue
        if job is not None:
            enqueued.append(job)
    logger.info(
        "build enqueue after activation kb=%s source=%s version=%s jobs=%s",
        kb.id,
        source_file_id,
        version_id,
        [j.id for j in enqueued],
    )
    return enqueued


async def claim_next_build_job(
    db: AsyncSession, *, lease_owner: str
) -> tuple[KnowledgeBuildJob, str] | None:
    if not settings.KNOWLEDGE_V2_BUILD_ENABLED:
        return None
    claimed = await claim_next(
        db,
        KnowledgeBuildJob,
        statuses=[BuildJobStatus.queued.value],
        lease_owner=lease_owner,
        lease_seconds=LEASE_SECONDS,
        order_by=(
            KnowledgeBuildJob.next_run_at.asc().nullsfirst(),
            KnowledgeBuildJob.created_at.asc(),
        ),
        commit=True,
    )
    if claimed is None:
        return None
    job, lease_token = claimed
    job.status = BuildJobStatus.running.value
    job.attempt_count = int(job.attempt_count or 0) + 1
    await db.commit()
    await db.refresh(job)
    return job, lease_token


async def process_build_job(db: AsyncSession, job: KnowledgeBuildJob) -> None:
    from app.models.knowledge_base import KnowledgeBase

    kb = await db.get(KnowledgeBase, job.knowledge_base_id)
    if kb is None or kb.deleted_at is not None:
        job.status = BuildJobStatus.failed.value
        job.error_code = "kb_missing"
        job.error_message = "knowledge base missing"
        job.finished_at = datetime.now(UTC)
        await db.flush()
        return

    state = await index_state_service.get_or_create_state(
        db,
        org_id=job.org_id,
        knowledge_base_id=job.knowledge_base_id,
        index_type=job.index_type,
    )
    await index_state_service.set_state_status(
        db,
        state,
        IndexStateStatus.unsupported.value,
        build_job_id=job.id,
        error="runtime_public_api_unavailable",
    )
    job.stage_results = {
        "result": "unsupported",
        "reason": "no_stable_public_api",
        "index_type": job.index_type,
    }
    job.status = BuildJobStatus.completed.value
    job.progress = 100
    job.finished_at = datetime.now(UTC)
    await db.flush()


async def finalize_build_job(
    db: AsyncSession,
    job: KnowledgeBuildJob,
    *,
    lease_owner: str,
    lease_token: str,
) -> bool:
    return await clear_lease_if_owner(
        db,
        KnowledgeBuildJob,
        job_id=job.id,
        lease_owner=lease_owner,
        lease_token=lease_token,
        values={
            "status": job.status,
            "progress": job.progress,
            "error_code": job.error_code,
            "error_message": job.error_message,
            "stage_results": job.stage_results,
            "finished_at": job.finished_at,
            "attempt_count": job.attempt_count,
        },
    )

"""Build orchestrator — enqueue and process KnowledgeBuildJob (not IngestionJob)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.base import not_deleted
from app.models.build_job import KnowledgeBuildJob
from app.models.enums import BuildJobStatus, BuildTriggerPolicy, IndexStateStatus, IndexType, KnowledgeBaseStatus
from app.services import build_executors, build_profile_service, index_state_service, runtime_binding_service
from app.services.index_registry import get_descriptor, is_runtime_supported
from app.workers.job_leasing import claim_next, clear_lease_if_owner

from app.services.build_input_manifest_service import BuildDelta, compute_build_delta

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
    target_kind: str = "index",
    target_key: str | None = None,
    input_manifest_hash: str | None = None,
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
        target_kind=target_kind,
        target_key=target_key or index_type,
        input_manifest_hash=input_manifest_hash,
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
    from app.services import build_input_manifest_service

    manifest_hash, _items, manifest_summary = await build_input_manifest_service.compute_manifest(db, kb)
    if not settings.KNOWLEDGE_V2_BUILD_ENABLED:
        await index_state_service.mark_indexes_stale(
            db,
            org_id=org_id,
            kb=kb,
            input_manifest_hash=manifest_hash,
            input_manifest_summary=manifest_summary,
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
        input_manifest_hash=manifest_hash,
        input_manifest_summary=manifest_summary,
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
                input_manifest_hash=manifest_hash,
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
                input_manifest_hash=manifest_hash,
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


# @lat: [[knowledge-objects#Build Job]]
async def process_build_job(db: AsyncSession, job: KnowledgeBuildJob) -> None:
    from app.models.knowledge_base import KnowledgeBase

    started_at = datetime.now(UTC)
    kb = await db.get(KnowledgeBase, job.knowledge_base_id)
    if kb is None or kb.deleted_at is not None:
        job.status = BuildJobStatus.failed.value
        job.error_code = "kb_missing"
        job.error_message = "knowledge base missing"
        job.finished_at = datetime.now(UTC)
        job.stage_results = _stage_results_payload(
            index_type=job.index_type,
            status="failed",
            started_at=started_at,
            finished_at=job.finished_at,
            attempt=int(job.attempt_count or 0),
            error_code=job.error_code,
            error_message=job.error_message,
        )
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
        IndexStateStatus.building.value,
        build_job_id=job.id,
    )

    binding = await runtime_binding_service.get_binding(db, job.knowledge_base_id)
    capabilities = (binding.capabilities if binding else None) or {}

    if not is_runtime_supported(job.index_type, capabilities):
        finished_at = datetime.now(UTC)
        await index_state_service.set_state_status(
            db,
            state,
            IndexStateStatus.unsupported.value,
            build_job_id=job.id,
            error="runtime_public_api_unavailable",
        )
        job.stage_results = _stage_results_payload(
            index_type=job.index_type,
            status="unsupported",
            started_at=started_at,
            finished_at=finished_at,
            attempt=int(job.attempt_count or 0),
            error_code="runtime_public_api_unavailable",
            error_message="no stable public API",
            output={"reason": "no_stable_public_api"},
        )
        job.status = BuildJobStatus.completed.value
        job.progress = 100
        job.error_code = None
        job.error_message = None
        job.finished_at = finished_at
        await db.flush()
        return

    reconcile_output: dict | None = None
    if binding is not None and job.index_type != IndexType.chunk.value:
        from app.runtime.ragflow import RagflowRuntimeAdapter
        from app.services import reconciliation_service

        adapter = RagflowRuntimeAdapter()
        try:
            reconcile_output = await reconciliation_service.reconcile_binding_config(
                db,
                job.knowledge_base_id,
                adapter,
            )
        finally:
            await adapter.aclose()

    executor = build_executors.EXECUTORS.get(job.index_type)
    if executor is None:
        finished_at = datetime.now(UTC)
        await index_state_service.set_state_status(
            db,
            state,
            IndexStateStatus.failed.value,
            build_job_id=job.id,
            error="executor_unavailable",
        )
        job.stage_results = _stage_results_payload(
            index_type=job.index_type,
            status="failed",
            started_at=started_at,
            finished_at=finished_at,
            attempt=int(job.attempt_count or 0),
            error_code="executor_unavailable",
            error_message="no build executor registered for index type",
        )
        job.status = BuildJobStatus.failed.value
        job.error_code = "executor_unavailable"
        job.error_message = "no build executor registered for index type"
        job.progress = 100
        job.finished_at = finished_at
        await db.flush()
        return

    try:
        result = await executor(db, job, kb)
    except Exception as exc:
        finished_at = datetime.now(UTC)
        retryable = True
        if _should_retry_job(job, retryable):
            _requeue_build_job(job, finished_at=finished_at)
            await index_state_service.set_state_status(
                db,
                state,
                IndexStateStatus.stale.value,
                build_job_id=job.id,
                error=str(exc),
            )
            job.stage_results = _stage_results_payload(
                index_type=job.index_type,
                status="failed",
                started_at=started_at,
                finished_at=finished_at,
                attempt=int(job.attempt_count or 0),
                error_code="stage_exception",
                error_message=str(exc),
                output={"retry_scheduled": True},
            )
        else:
            await _mark_build_failed(
                db,
                job=job,
                kb=kb,
                state=state,
                started_at=started_at,
                finished_at=finished_at,
                error_code="stage_exception",
                error_message=str(exc),
            )
        await db.flush()
        return

    finished_at = datetime.now(UTC)
    if result.status == "succeeded":
        from app.services import build_input_manifest_service

        manifest_hash, _items, manifest_summary = await build_input_manifest_service.compute_manifest(
            db, kb
        )
        job.input_manifest_hash = manifest_hash
        await index_state_service.set_state_status(
            db,
            state,
            IndexStateStatus.ready.value,
            build_job_id=job.id,
            capabilities=capabilities,
            input_manifest_hash=manifest_hash,
            input_manifest_summary=manifest_summary,
        )
        if result.validation_payload is not None or result.coverage_payload is not None:
            await index_state_service.persist_validation(
                state,
                validation_payload=result.validation_payload,
                coverage_payload=result.coverage_payload,
            )
        stage_output = dict(result.output)
        if reconcile_output:
            stage_output["runtime_config_revision"] = reconcile_output.get("config_revision")
            stage_output["config_reconcile"] = {
                "drift_status": reconcile_output.get("drift_status"),
                "applied": reconcile_output.get("applied"),
            }
        job.stage_results = _stage_results_payload(
            index_type=job.index_type,
            status="succeeded",
            started_at=started_at,
            finished_at=finished_at,
            attempt=int(job.attempt_count or 0),
            output=stage_output,
        )
        job.status = BuildJobStatus.completed.value
        job.progress = 100
        job.error_code = None
        job.error_message = None
        job.finished_at = finished_at
        if kb.status == KnowledgeBaseStatus.degraded.value:
            kb.status = KnowledgeBaseStatus.active.value
            kb.last_error = None
        await db.flush()
        return

    if _should_retry_job(job, result.retryable):
        _requeue_build_job(job, finished_at=finished_at)
        await index_state_service.set_state_status(
            db,
            state,
            IndexStateStatus.stale.value,
            build_job_id=job.id,
            error=result.error_message,
        )
        job.stage_results = _stage_results_payload(
            index_type=job.index_type,
            status="failed",
            started_at=started_at,
            finished_at=finished_at,
            attempt=int(job.attempt_count or 0),
            error_code=result.error_code,
            error_message=result.error_message,
            output={**result.output, "retry_scheduled": True},
        )
        await db.flush()
        return

    await _mark_build_failed(
        db,
        job=job,
        kb=kb,
        state=state,
        started_at=started_at,
        finished_at=finished_at,
        error_code=result.error_code or "stage_failed",
        error_message=result.error_message or "build stage failed",
        output=result.output,
    )
    if result.validation_payload is not None or result.coverage_payload is not None:
        await index_state_service.persist_validation(
            state,
            validation_payload=result.validation_payload,
            coverage_payload=result.coverage_payload,
        )
    await db.flush()


def _stage_results_payload(
    *,
    index_type: str,
    status: str,
    started_at: datetime,
    finished_at: datetime,
    attempt: int,
    error_code: str | None = None,
    error_message: str | None = None,
    output: dict | None = None,
) -> dict:
    return {
        "stage": index_type,
        "status": status,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "attempt": attempt,
        "error_code": error_code,
        "error_message": error_message,
        "output": output or {},
    }


def _should_retry_job(job: KnowledgeBuildJob, retryable: bool) -> bool:
    if not retryable:
        return False
    max_attempts = min(int(job.max_attempts or settings.KNOWLEDGE_BUILD_MAX_ATTEMPTS), settings.KNOWLEDGE_BUILD_MAX_ATTEMPTS)
    return int(job.attempt_count or 0) < max_attempts


def _requeue_build_job(job: KnowledgeBuildJob, *, finished_at: datetime) -> None:
    attempt = int(job.attempt_count or 0)
    backoff = settings.KNOWLEDGE_BUILD_RETRY_BACKOFF_SECONDS * max(attempt, 1)
    job.status = BuildJobStatus.queued.value
    job.next_run_at = finished_at + timedelta(seconds=backoff)
    job.finished_at = None
    job.error_code = None
    job.error_message = None
    job.progress = max(int(job.progress or 0), 10)


async def _mark_build_failed(
    db: AsyncSession,
    *,
    job: KnowledgeBuildJob,
    kb,
    state,
    started_at: datetime,
    finished_at: datetime,
    error_code: str,
    error_message: str,
    output: dict | None = None,
) -> None:
    await index_state_service.set_state_status(
        db,
        state,
        IndexStateStatus.failed.value,
        build_job_id=job.id,
        error=error_code,
    )
    job.stage_results = _stage_results_payload(
        index_type=job.index_type,
        status="failed",
        started_at=started_at,
        finished_at=finished_at,
        attempt=int(job.attempt_count or 0),
        error_code=error_code,
        error_message=error_message,
        output=output or {},
    )
    job.status = BuildJobStatus.failed.value
    job.error_code = error_code
    job.error_message = error_message
    job.progress = 100
    job.finished_at = finished_at
    if job.index_type == IndexType.chunk.value:
        kb.status = KnowledgeBaseStatus.degraded.value
        kb.last_error = error_message


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
            "next_run_at": job.next_run_at,
        },
    )

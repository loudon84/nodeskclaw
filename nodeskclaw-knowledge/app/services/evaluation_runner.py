"""Deterministic retrieval metrics and evaluation run execution."""

from __future__ import annotations

import logging
from typing import Any
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.ragflow.client import RagflowClient
from app.models.base import not_deleted
from app.models.enums import EvaluationRunStatus, RetrievalOrigin
from app.models.evaluation import EvaluationCase, EvaluationResult, EvaluationRun, EvaluationSet
from app.models.retrieval_profile import RetrievalProfile
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_set_service, retrieval_service
from app.services.permission_service import build_access_plan
from app.services.retrieval_profile_service import merge_profile_config
from app.workers.job_leasing import utc_now

logger = logging.getLogger(__name__)

DEFAULT_K = 8


def hit_at_k(returned_ids: Sequence[str], expected_ids: Sequence[str], k: int) -> float:
    if not expected_ids or k <= 0:
        return 0.0
    top = list(returned_ids)[:k]
    expected = set(expected_ids)
    return 1.0 if any(item in expected for item in top) else 0.0


def recall_at_k(returned_ids: Sequence[str], expected_ids: Sequence[str], k: int) -> float:
    if not expected_ids or k <= 0:
        return 0.0
    top = set(list(returned_ids)[:k])
    hits = sum(1 for item in expected_ids if item in top)
    return hits / len(expected_ids)


def mean_reciprocal_rank(returned_ids: Sequence[str], expected_ids: Sequence[str]) -> float:
    if not expected_ids:
        return 0.0
    expected = set(expected_ids)
    for index, item in enumerate(returned_ids, start=1):
        if item in expected:
            return 1.0 / index
    return 0.0


def expected_source_hit(returned_ids: Sequence[str], expected_ids: Sequence[str], k: int) -> float:
    return hit_at_k(returned_ids, expected_ids, k)


def has_unauthorized_source(
    returned_ids: Sequence[str],
    allowed_source_file_ids: set[str],
) -> bool:
    if not returned_ids:
        return False
    if not allowed_source_file_ids:
        return True
    return any(item not in allowed_source_file_ids for item in returned_ids)


def _unique_source_ids(chunks: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        sid = chunk.get("source_file_id")
        if not sid or sid in seen:
            continue
        seen.add(sid)
        ids.append(str(sid))
    return ids


def _aggregate_metrics(results: list[EvaluationResult], *, k: int) -> dict[str, Any]:
    count = len(results)
    if count == 0:
        return {
            "hit_at_k": 0.0,
            "hit_at_8": 0.0,
            "recall_at_k": 0.0,
            "mrr": 0.0,
            "expected_source_hit": 0.0,
            "avg_latency_ms": 0.0,
            "empty_rate": 0.0,
            "degraded_rate": 0.0,
            "unauthorized_rate": 0.0,
            "case_count": 0,
            "k": k,
        }
    empty = sum(1 for item in results if not item.returned_source_file_ids)
    degraded = sum(
        1 for item in results if (item.details or {}).get("execution_status") == "degraded"
    )
    unauthorized = sum(1 for item in results if item.unauthorized_hit)
    return {
        "hit_at_k": sum(item.hit_at_k for item in results) / count,
        "hit_at_8": sum(item.hit_at_k for item in results) / count,
        "recall_at_k": sum(item.recall_at_k for item in results) / count,
        "mrr": sum(item.mrr for item in results) / count,
        "expected_source_hit": sum(
            float((item.details or {}).get("expected_source_hit", item.hit_at_k)) for item in results
        )
        / count,
        "avg_latency_ms": sum(item.latency_ms for item in results) / count,
        "empty_rate": empty / count,
        "degraded_rate": degraded / count,
        "unauthorized_rate": unauthorized / count,
        "case_count": count,
        "k": k,
    }


async def process_evaluation_run(
    db: AsyncSession,
    ragflow: RagflowClient,
    run: EvaluationRun,
) -> None:
    eval_set = await db.get(EvaluationSet, run.evaluation_set_id)
    if eval_set is None or eval_set.deleted_at is not None:
        run.status = EvaluationRunStatus.failed.value
        run.last_error = "evaluation set missing"
        run.finished_at = utc_now()
        return

    profile = await db.get(RetrievalProfile, run.retrieval_profile_id)
    if profile is None or profile.deleted_at is not None:
        run.status = EvaluationRunStatus.failed.value
        run.last_error = "retrieval profile missing"
        run.finished_at = utc_now()
        return

    config = merge_profile_config(profile.config)
    k = int(config.get("top_n", DEFAULT_K))

    snapshot = run.principal_snapshot if isinstance(getattr(run, "principal_snapshot", None), dict) else None
    if not snapshot:
        run.status = EvaluationRunStatus.failed.value
        run.last_error = "principal_snapshot missing"
        run.finished_at = utc_now()
        return

    member = KnowledgePrincipal(
        user_id=str(snapshot.get("user_id") or snapshot.get("member_id") or run.created_by_member_id),
        member_id=str(snapshot.get("member_id") or run.created_by_member_id),
        org_id=str(snapshot.get("org_id") or eval_set.org_id),
        name=str(snapshot.get("name") or ""),
        employee_no=snapshot.get("employee_no"),
        department=snapshot.get("department"),
        job_title=snapshot.get("job_title"),
        member_role=str(snapshot.get("member_role") or "member"),
        supervisor_member_id=snapshot.get("supervisor_member_id"),
        is_active=bool(snapshot.get("is_active", True)),
        is_super_admin=bool(snapshot.get("is_super_admin", False)),
    )

    cases_result = await db.execute(
        select(EvaluationCase)
        .where(
            EvaluationCase.evaluation_set_id == run.evaluation_set_id,
            not_deleted(EvaluationCase),
        )
        .order_by(EvaluationCase.created_at.asc())
    )
    cases = list(cases_result.scalars().all())
    if not cases:
        run.status = EvaluationRunStatus.failed.value
        run.last_error = "no evaluation cases"
        run.finished_at = utc_now()
        return

    kbs = await knowledge_set_service.list_bound_knowledge_bases(db, member, eval_set.knowledge_set_id)
    access_plan = await build_access_plan(db, member, kbs)
    allowed_ids = set(access_plan.source_file_ids)

    results: list[EvaluationResult] = []
    for case in cases:
        expected_ids = [str(item) for item in (case.expected_source_file_ids or [])]
        try:
            case_started = utc_now()
            payload = await retrieval_service.retrieve(
                db,
                member,
                ragflow,
                knowledge_set_id=eval_set.knowledge_set_id,
                query=case.query,
                origin=RetrievalOrigin.evaluation.value,
                profile_id=run.retrieval_profile_id,
            )
            chunks = payload.get("chunks") or []
            returned_ids = _unique_source_ids(chunks)
            execution_status = str(payload.get("status") or "success")
            latency_ms = int(payload.get("latency_ms") or 0)
            if latency_ms <= 0:
                latency_ms = int((utc_now() - case_started).total_seconds() * 1000)
        except Exception as exc:
            logger.exception("evaluation case failed run_id=%s case_id=%s", run.id, case.id)
            run.attempt_count += 1
            run.last_error = str(exc)
            if run.attempt_count >= run.max_attempts:
                run.status = EvaluationRunStatus.failed.value
                run.finished_at = utc_now()
            else:
                run.status = EvaluationRunStatus.pending.value
                run.next_run_at = utc_now()
            return

        unauthorized = has_unauthorized_source(returned_ids, allowed_ids)
        result = EvaluationResult(
            run_id=run.id,
            case_id=case.id,
            hit_at_k=hit_at_k(returned_ids, expected_ids, k),
            recall_at_k=recall_at_k(returned_ids, expected_ids, k),
            mrr=mean_reciprocal_rank(returned_ids, expected_ids),
            latency_ms=latency_ms,
            returned_source_file_ids=returned_ids,
            unauthorized_hit=unauthorized,
            details={
                "expected_source_hit": expected_source_hit(returned_ids, expected_ids, k),
                "execution_status": execution_status,
                "k": k,
                "effective_indexes": (payload.get("capability_plan") or {}).get("effective_indexes"),
                "query_type": (payload.get("capability_plan") or {}).get("query_type"),
                "fallback_used": (payload.get("capability_plan") or {}).get("fallback_used"),
            },
        )
        db.add(result)
        results.append(result)
        if unauthorized:
            run.metrics = _aggregate_metrics(results, k=k)
            run.status = EvaluationRunStatus.failed.value
            run.last_error = "errors.knowledge.evaluation_failed"
            run.finished_at = utc_now()
            return

    run.metrics = _aggregate_metrics(results, k=k)
    if results:
        sample_details = results[0].details or {}
        run.metrics = {
            **(run.metrics or {}),
            "effective_indexes": sample_details.get("effective_indexes"),
            "query_type": sample_details.get("query_type"),
        }
    run.status = EvaluationRunStatus.completed.value
    run.last_error = None
    run.finished_at = utc_now()
    run.next_run_at = None

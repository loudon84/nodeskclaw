"""Evaluation set/case CRUD, runs, compare."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.enums import EvaluationRunStatus, SetPermission
from app.models.evaluation import EvaluationCase, EvaluationResult, EvaluationRun, EvaluationSet
from app.models.retrieval_profile import RetrievalProfile
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_set_service
from app.services.permission_service import has_set_permission
from app.workers.job_leasing import claim_next

LEASE_SECONDS = 120
DEFAULT_K = 8


def build_principal_snapshot(member: KnowledgePrincipal) -> dict[str, Any]:
    return {
        "user_id": member.user_id,
        "member_id": member.member_id,
        "org_id": member.org_id,
        "name": member.name,
        "employee_no": member.employee_no,
        "department": member.department,
        "job_title": member.job_title,
        "member_role": member.member_role,
        "supervisor_member_id": member.supervisor_member_id,
        "is_active": member.is_active,
        "is_super_admin": member.is_super_admin,
    }


async def _require_set_manage(
    db: AsyncSession,
    member: KnowledgePrincipal,
    knowledge_set_id: str,
):
    ks = await knowledge_set_service.get_knowledge_set(db, member, knowledge_set_id)
    if not await has_set_permission(db, member, ks, SetPermission.manage.value):
        raise ForbiddenError()
    return ks


async def _get_eval_set_or_404(db: AsyncSession, evaluation_set_id: str) -> EvaluationSet:
    row = await db.get(EvaluationSet, evaluation_set_id)
    if row is None or row.deleted_at is not None:
        raise NotFoundError(message="评测集不存在", message_key="errors.knowledge.evaluation_set_not_found")
    return row


async def _require_eval_set_manage(
    db: AsyncSession,
    member: KnowledgePrincipal,
    evaluation_set_id: str,
) -> EvaluationSet:
    row = await _get_eval_set_or_404(db, evaluation_set_id)
    if row.org_id != member.org_id and not member.is_super_admin:
        raise NotFoundError(message="评测集不存在", message_key="errors.knowledge.evaluation_set_not_found")
    await _require_set_manage(db, member, row.knowledge_set_id)
    return row


async def create_evaluation_set(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    knowledge_set_id: str,
    name: str,
    description: str | None = None,
) -> EvaluationSet:
    await _require_set_manage(db, member, knowledge_set_id)
    row = EvaluationSet(
        org_id=member.org_id,
        knowledge_set_id=knowledge_set_id,
        name=name,
        description=description,
        created_by_member_id=member.member_id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_evaluation_sets(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    knowledge_set_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[EvaluationSet], int]:
    conds = [EvaluationSet.org_id == member.org_id, not_deleted(EvaluationSet)]
    if knowledge_set_id:
        await _require_set_manage(db, member, knowledge_set_id)
        conds.append(EvaluationSet.knowledge_set_id == knowledge_set_id)
        total = int(
            (await db.execute(select(func.count()).select_from(EvaluationSet).where(*conds))).scalar_one()
        )
        result = await db.execute(
            select(EvaluationSet)
            .where(*conds)
            .order_by(EvaluationSet.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    result = await db.execute(
        select(EvaluationSet).where(*conds).order_by(EvaluationSet.created_at.desc())
    )
    rows = list(result.scalars().all())
    filtered: list[EvaluationSet] = []
    for item in rows:
        try:
            ks = await knowledge_set_service.get_knowledge_set(db, member, item.knowledge_set_id)
        except Exception:
            continue
        if await has_set_permission(db, member, ks, SetPermission.manage.value):
            filtered.append(item)
    total = len(filtered)
    start = (page - 1) * page_size
    return filtered[start : start + page_size], total


async def get_evaluation_set(
    db: AsyncSession,
    member: KnowledgePrincipal,
    evaluation_set_id: str,
) -> EvaluationSet:
    return await _require_eval_set_manage(db, member, evaluation_set_id)


async def update_evaluation_set(
    db: AsyncSession,
    member: KnowledgePrincipal,
    evaluation_set_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
) -> EvaluationSet:
    row = await _require_eval_set_manage(db, member, evaluation_set_id)
    if name is not None:
        row.name = name
    if description is not None:
        row.description = description
    await db.commit()
    await db.refresh(row)
    return row


async def delete_evaluation_set(
    db: AsyncSession,
    member: KnowledgePrincipal,
    evaluation_set_id: str,
) -> None:
    row = await _require_eval_set_manage(db, member, evaluation_set_id)
    row.soft_delete()
    await db.commit()


async def create_case(
    db: AsyncSession,
    member: KnowledgePrincipal,
    evaluation_set_id: str,
    *,
    query: str,
    expected_source_file_ids: list[str],
    expected_keywords: list[str] | None = None,
    expected_answer: str | None = None,
) -> EvaluationCase:
    await _require_eval_set_manage(db, member, evaluation_set_id)
    if not expected_source_file_ids:
        raise BadRequestError(
            message="expected_source_file_ids 不能为空",
            message_key="errors.common.validation_error",
        )
    row = EvaluationCase(
        evaluation_set_id=evaluation_set_id,
        query=query,
        expected_source_file_ids=list(expected_source_file_ids),
        expected_keywords=list(expected_keywords) if expected_keywords is not None else None,
        expected_answer=expected_answer,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_cases(
    db: AsyncSession,
    member: KnowledgePrincipal,
    evaluation_set_id: str,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[EvaluationCase], int]:
    await _require_eval_set_manage(db, member, evaluation_set_id)
    conds = [EvaluationCase.evaluation_set_id == evaluation_set_id, not_deleted(EvaluationCase)]
    total = int(
        (await db.execute(select(func.count()).select_from(EvaluationCase).where(*conds))).scalar_one()
    )
    result = await db.execute(
        select(EvaluationCase)
        .where(*conds)
        .order_by(EvaluationCase.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def get_case(
    db: AsyncSession,
    member: KnowledgePrincipal,
    case_id: str,
) -> EvaluationCase:
    row = await db.get(EvaluationCase, case_id)
    if row is None or row.deleted_at is not None:
        raise NotFoundError(message="评测用例不存在", message_key="errors.knowledge.evaluation_case_not_found")
    await _require_eval_set_manage(db, member, row.evaluation_set_id)
    return row


async def update_case(
    db: AsyncSession,
    member: KnowledgePrincipal,
    case_id: str,
    *,
    query: str | None = None,
    expected_source_file_ids: list[str] | None = None,
    expected_keywords: list[str] | None = None,
    expected_answer: str | None = None,
) -> EvaluationCase:
    row = await get_case(db, member, case_id)
    if query is not None:
        row.query = query
    if expected_source_file_ids is not None:
        if not expected_source_file_ids:
            raise BadRequestError(
                message="expected_source_file_ids 不能为空",
                message_key="errors.common.validation_error",
            )
        row.expected_source_file_ids = list(expected_source_file_ids)
    if expected_keywords is not None:
        row.expected_keywords = list(expected_keywords)
    if expected_answer is not None:
        row.expected_answer = expected_answer
    await db.commit()
    await db.refresh(row)
    return row


async def delete_case(
    db: AsyncSession,
    member: KnowledgePrincipal,
    case_id: str,
) -> None:
    row = await get_case(db, member, case_id)
    row.soft_delete()
    await db.commit()


async def create_run(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    evaluation_set_id: str,
    retrieval_profile_id: str,
) -> EvaluationRun:
    eval_set = await _require_eval_set_manage(db, member, evaluation_set_id)
    profile = await db.get(RetrievalProfile, retrieval_profile_id)
    if profile is None or profile.deleted_at is not None:
        raise NotFoundError(message="检索配置不存在", message_key="errors.knowledge.profile_not_found")
    if profile.knowledge_set_id != eval_set.knowledge_set_id:
        raise BadRequestError(
            message="检索配置不属于该知识集合",
            message_key="errors.knowledge.profile_not_found",
        )
    case_count = int(
        (
            await db.execute(
                select(func.count()).select_from(EvaluationCase).where(
                    EvaluationCase.evaluation_set_id == evaluation_set_id,
                    not_deleted(EvaluationCase),
                )
            )
        ).scalar_one()
    )
    if case_count == 0:
        raise BadRequestError(
            message="评测集没有用例",
            message_key="errors.common.validation_error",
        )
    row = EvaluationRun(
        evaluation_set_id=evaluation_set_id,
        retrieval_profile_id=retrieval_profile_id,
        status=EvaluationRunStatus.pending.value,
        metrics=None,
        principal_snapshot=build_principal_snapshot(member),
        created_by_member_id=member.member_id,
        attempt_count=0,
        max_attempts=5,
        next_run_at=datetime.now(UTC),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_runs(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    evaluation_set_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[EvaluationRun], int]:
    if evaluation_set_id:
        await _require_eval_set_manage(db, member, evaluation_set_id)
        conds = [
            EvaluationRun.evaluation_set_id == evaluation_set_id,
            not_deleted(EvaluationRun),
        ]
    else:
        set_ids_result = await db.execute(
            select(EvaluationSet.id).where(
                EvaluationSet.org_id == member.org_id,
                not_deleted(EvaluationSet),
            )
        )
        set_ids = [row[0] for row in set_ids_result.all()]
        if not set_ids:
            return [], 0
        conds = [EvaluationRun.evaluation_set_id.in_(set_ids), not_deleted(EvaluationRun)]
    total = int(
        (await db.execute(select(func.count()).select_from(EvaluationRun).where(*conds))).scalar_one()
    )
    result = await db.execute(
        select(EvaluationRun)
        .where(*conds)
        .order_by(EvaluationRun.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def get_run(
    db: AsyncSession,
    member: KnowledgePrincipal,
    run_id: str,
) -> EvaluationRun:
    row = await db.get(EvaluationRun, run_id)
    if row is None or row.deleted_at is not None:
        raise NotFoundError(message="评测运行不存在", message_key="errors.knowledge.evaluation_run_not_found")
    await _require_eval_set_manage(db, member, row.evaluation_set_id)
    return row


async def list_results(
    db: AsyncSession,
    member: KnowledgePrincipal,
    run_id: str,
) -> list[EvaluationResult]:
    await get_run(db, member, run_id)
    result = await db.execute(
        select(EvaluationResult)
        .where(EvaluationResult.run_id == run_id, not_deleted(EvaluationResult))
        .order_by(EvaluationResult.created_at.asc())
    )
    return list(result.scalars().all())


def _metric_snapshot(metrics: dict[str, Any] | None) -> dict[str, float]:
    m = metrics or {}
    return {
        "hit_at_8": float(m.get("hit_at_k", m.get("hit_at_8", 0.0))),
        "mrr": float(m.get("mrr", 0.0)),
        "avg_latency_ms": float(m.get("avg_latency_ms", 0.0)),
        "empty_rate": float(m.get("empty_rate", 0.0)),
        "degraded_rate": float(m.get("degraded_rate", 0.0)),
    }


async def compare_profiles(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    evaluation_set_id: str,
    profile_a_id: str | None = None,
    profile_b_id: str | None = None,
    run_a_id: str | None = None,
    run_b_id: str | None = None,
) -> dict[str, Any]:
    await _require_eval_set_manage(db, member, evaluation_set_id)

    async def _resolve_completed_run(
        *,
        run_id: str | None,
        profile_id: str | None,
    ) -> EvaluationRun:
        if run_id:
            run = await get_run(db, member, run_id)
            if run.evaluation_set_id != evaluation_set_id:
                raise BadRequestError(
                    message="运行不属于该评测集",
                    message_key="errors.common.bad_request",
                )
            if run.status != EvaluationRunStatus.completed.value:
                raise BadRequestError(
                    message="评测运行尚未完成",
                    message_key="errors.knowledge.evaluation_failed",
                )
            return run
        if not profile_id:
            raise BadRequestError(
                message="需要提供 run_id 或 profile_id",
                message_key="errors.common.validation_error",
            )
        result = await db.execute(
            select(EvaluationRun)
            .where(
                EvaluationRun.evaluation_set_id == evaluation_set_id,
                EvaluationRun.retrieval_profile_id == profile_id,
                EvaluationRun.status == EvaluationRunStatus.completed.value,
                not_deleted(EvaluationRun),
            )
            .order_by(EvaluationRun.finished_at.desc().nullslast(), EvaluationRun.created_at.desc())
            .limit(1)
        )
        run = result.scalar_one_or_none()
        if run is None:
            raise NotFoundError(
                message="未找到已完成的评测运行",
                message_key="errors.knowledge.evaluation_run_not_found",
            )
        return run

    run_a = await _resolve_completed_run(run_id=run_a_id, profile_id=profile_a_id)
    run_b = await _resolve_completed_run(run_id=run_b_id, profile_id=profile_b_id)
    return {
        "evaluation_set_id": evaluation_set_id,
        "profile_a": {
            "run_id": run_a.id,
            "retrieval_profile_id": run_a.retrieval_profile_id,
            "metrics": _metric_snapshot(run_a.metrics),
        },
        "profile_b": {
            "run_id": run_b.id,
            "retrieval_profile_id": run_b.retrieval_profile_id,
            "metrics": _metric_snapshot(run_b.metrics),
        },
        "delta": {
            key: round(
                _metric_snapshot(run_b.metrics)[key] - _metric_snapshot(run_a.metrics)[key],
                6,
            )
            for key in ("hit_at_8", "mrr", "avg_latency_ms", "empty_rate", "degraded_rate")
        },
    }


async def claim_next_evaluation_run(db: AsyncSession, *, lease_owner: str) -> EvaluationRun | None:
    run = await claim_next(
        db,
        EvaluationRun,
        statuses=[EvaluationRunStatus.pending.value, EvaluationRunStatus.running.value],
        lease_owner=lease_owner,
        lease_seconds=LEASE_SECONDS,
        order_by=(EvaluationRun.next_run_at.asc().nullsfirst(), EvaluationRun.created_at.asc()),
    )
    if run is None:
        return None
    if run.status == EvaluationRunStatus.pending.value:
        run.status = EvaluationRunStatus.running.value
    await db.flush()
    return run

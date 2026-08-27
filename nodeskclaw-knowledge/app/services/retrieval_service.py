"""Secure retrieval pipeline with planner and merge."""

from __future__ import annotations

import hashlib
import time
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError, ServiceUnavailableError
from app.integrations.ragflow.client import RagflowClient
from app.models.enums import (
    AccessPlanKind,
    ApplicationPermission,
    ApplicationStatus,
    KnowledgeSetStatus,
    ProfileStatus,
    RetrievalOrigin,
    SetPermission,
    SourceSyncState,
)
from app.models.retrieval_audit import RetrievalAudit
from app.models.chat_citation import ChatCitation
from app.models.source_file import SourceFile
from app.schemas.knowledge import RetrievalOptions
from app.schemas.principal import KnowledgePrincipal
from app.services import (
    knowledge_set_service,
    metrics_service,
    retrieval_merge_service,
    retrieval_planner,
    retrieval_profile_service,
    retrieval_trace_service,
    runtime_binding_service,
)
from app.services.permission_service import (
    build_access_plan,
    has_application_permission,
    has_set_permission,
)
from app.services.retrieval_profile_service import merge_profile_config


def _observe_retrieval(status: str, started: float) -> None:
    metrics_service.observe_retrieval(status=status, duration_seconds=time.perf_counter() - started)


def _audit_capability_fields(capability_plan, *, fallback_used: bool | None = None) -> dict:
    from app.services.capability_planner import CapabilityPlan

    if not isinstance(capability_plan, CapabilityPlan):
        return {}
    return {
        "query_type": capability_plan.query_type,
        "requested_indexes": list(capability_plan.requested_indexes),
        "effective_indexes": list(capability_plan.effective_indexes),
        "fallback_used": fallback_used if fallback_used is not None else capability_plan.fallback_used,
    }


async def _dataset_id_by_kb_id(db: AsyncSession, knowledge_bases: list) -> dict[str, str]:
    out: dict[str, str] = {}
    for kb in knowledge_bases:
        dataset_id = await runtime_binding_service.get_dataset_id(db, kb)
        if dataset_id:
            out[kb.id] = dataset_id
    return out


def _extract_page(positions: list | None) -> int | None:
    if not positions:
        return None
    first = positions[0]
    if isinstance(first, (list, tuple)) and first:
        try:
            return int(first[0])
        except (TypeError, ValueError):
            return None
    if isinstance(first, dict) and "page" in first:
        try:
            return int(first["page"])
        except (TypeError, ValueError):
            return None
    return None


def _compute_source_freshness(source_file) -> str:
    if source_file is None:
        return "unknown"
    sync_state = getattr(source_file, "sync_state", None)
    if sync_state in {SourceSyncState.stale.value, SourceSyncState.error.value}:
        return "stale"
    last_synced = getattr(source_file, "last_synced_at", None)
    if last_synced is None:
        if getattr(source_file, "source_kind", None) == "connector":
            return "unknown"
        return "fresh"
    if last_synced.tzinfo is None:
        last_synced = last_synced.replace(tzinfo=UTC)
    age = (datetime.now(UTC) - last_synced).total_seconds()
    if age > int(settings.SOURCE_FRESHNESS_MAX_AGE_SECONDS):
        return "stale"
    return "fresh"


def _diagnostics_from_slices(slice_results: list) -> dict:
    return {
        "slice_count": len(slice_results),
        "successful_slice_count": sum(1 for item in slice_results if item.status == "success"),
        "failed_slice_count": sum(1 for item in slice_results if item.status == "failed"),
        "slices": [
            {
                "knowledge_base_id": item.knowledge_base_id,
                "dataset_id": item.dataset_id,
                "status": item.status,
                "latency_ms": item.latency_ms,
                "candidate_count": item.candidate_count,
                "safe_count": item.safe_count,
                "error_code": item.error_code,
            }
            for item in slice_results
        ],
    }


# @lat: [[knowledge#Secure Retrieval Pipeline]]
async def retrieve(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowClient,
    *,
    knowledge_set_id: str,
    query: str,
    options: RetrievalOptions | None = None,
    top_k: int | None = None,
    similarity_threshold: float | None = None,
    filters: dict[str, list] | None = None,
    origin: str = RetrievalOrigin.direct_retrieval.value,
    profile_id: str | None = None,
    application_id: str | None = None,
    include_capability_plan: bool = False,
) -> dict:
    if application_id:
        return await retrieve_for_application(
            db,
            member,
            ragflow,
            application_id=application_id,
            query=query,
            options=options,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            filters=filters,
            origin=origin,
            profile_id=profile_id,
        )
    result = await _retrieve_for_set(
        db,
        member,
        ragflow,
        knowledge_set_id=knowledge_set_id,
        query=query,
        options=options,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
        filters=filters,
        origin=origin,
        profile_id=profile_id,
    )
    if include_capability_plan or settings.KNOWLEDGE_V2_CAPABILITY_PLANNER_ENABLED:
        from app.services import capability_planner

        plan = capability_planner.build_capability_plan(query)
        result["capability_plan"] = plan.to_dict()
    return result


async def retrieve_for_application(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowClient,
    *,
    application_id: str,
    query: str,
    options: RetrievalOptions | None = None,
    top_k: int | None = None,
    similarity_threshold: float | None = None,
    filters: dict[str, list] | None = None,
    origin: str = RetrievalOrigin.direct_retrieval.value,
    profile_id: str | None = None,
) -> dict:
    from app.services import knowledge_application_service

    if not settings.KNOWLEDGE_V2_APPLICATION_ENABLED:
        raise BadRequestError(
            message="Knowledge Application 未启用",
            message_key="errors.knowledge.application_disabled",
        )
    app = await knowledge_application_service.get_application(db, member, application_id)
    if app.status == ApplicationStatus.disabled.value:
        raise ForbiddenError(
            message="应用已禁用",
            message_key="errors.knowledge.application_disabled",
        )
    if app.status != ApplicationStatus.active.value and origin != RetrievalOrigin.evaluation.value:
        raise ForbiddenError(
            message="应用未发布",
            message_key="errors.knowledge.application_not_active",
        )
    if not await has_application_permission(db, member, app, ApplicationPermission.use.value):
        raise ForbiddenError(
            message="无权使用该知识应用",
            message_key="errors.knowledge.retrieval_denied",
        )
    set_ids = await knowledge_application_service.list_bound_set_ids(db, application_id)
    if not set_ids:
        raise BadRequestError(
            message="应用未绑定知识集合",
            message_key="errors.knowledge.application_empty",
        )

    usable_set_ids: list[str] = []
    merged_kbs: list = []
    seen_kb: set[str] = set()
    weight_by_kb: dict[str, float] = {}
    for set_id in set_ids:
        try:
            ks = await knowledge_set_service.get_knowledge_set(db, member, set_id)
        except (NotFoundError, ForbiddenError):
            continue
        if ks.status == KnowledgeSetStatus.disabled.value:
            continue
        if not await has_set_permission(db, member, ks, SetPermission.use.value):
            continue
        usable_set_ids.append(set_id)
        for kb in await knowledge_set_service.list_bound_knowledge_bases(db, member, set_id):
            if kb.id not in seen_kb:
                seen_kb.add(kb.id)
                merged_kbs.append(kb)
        for item in await knowledge_set_service.list_set_items(db, member, set_id):
            prev = weight_by_kb.get(item.knowledge_base_id)
            w = float(item.weight)
            if prev is None or w > prev:
                weight_by_kb[item.knowledge_base_id] = w

    if not usable_set_ids:
        raise BadRequestError(
            message="应用没有可用的知识集合",
            message_key="errors.knowledge.application_empty",
        )
    if not merged_kbs:
        raise BadRequestError(
            message="应用未绑定知识库",
            message_key="errors.knowledge.application_empty",
        )

    merged_items = [
        SimpleNamespace(knowledge_base_id=kb_id, weight=weight)
        for kb_id, weight in weight_by_kb.items()
    ]

    resolved_profile_id = profile_id or app.active_profile_id
    result = await _retrieve_for_set(
        db,
        member,
        ragflow,
        knowledge_set_id=usable_set_ids[0],
        query=query,
        options=options,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
        filters=filters,
        origin=origin,
        profile_id=resolved_profile_id,
        kbs_override=merged_kbs,
        set_items_override=merged_items,
        bump_set_ids=usable_set_ids,
    )
    result["application_id"] = application_id
    result["answer_model"] = app.answer_model
    result["knowledge_set_ids"] = usable_set_ids
    if "capability_plan" not in result and settings.KNOWLEDGE_V2_CAPABILITY_PLANNER_ENABLED:
        from app.services import capability_planner

        result["capability_plan"] = capability_planner.build_capability_plan(query).to_dict()
    return result


def _evidence_response_payload(citation: ChatCitation, *, highlight: str | None = None) -> dict:
    runtime_payload = citation.runtime_payload or {}
    return {
        "evidence_id": citation.id,
        "evidence_type": citation.evidence_type,
        "content": citation.content,
        "score": citation.score,
        "source_refs": citation.source_refs or [],
        "payload": {
            "page": citation.page or runtime_payload.get("page"),
            "highlight": highlight if highlight is not None else runtime_payload.get("highlight"),
        },
    }


async def _persist_retrieval_evidence(
    db: AsyncSession,
    member: KnowledgePrincipal,
    merged: list,
    *,
    origin: str,
) -> tuple[list[dict], list[dict]]:
    chunks_out: list[dict] = []
    evidence_out: list[dict] = []
    for item in merged:
        chunk = item.chunk
        meta = chunk.document_metadata or {}
        sf_id = meta.get("nk_source_file_id")
        source_file = await db.get(SourceFile, sf_id) if sf_id else None
        last_synced_at = getattr(source_file, "last_synced_at", None) if source_file else None
        page = _extract_page(chunk.positions)
        evidence_type = meta.get("nk_evidence_type") or "chunk"
        source_refs = [
            {
                "source_file_id": meta.get("nk_source_file_id"),
                "file_version_id": meta.get("nk_file_version_id"),
                "knowledge_base_id": meta.get("nk_knowledge_base_id"),
            }
        ]
        runtime_payload = {
            "document_id": chunk.document_id,
            "chunk_id": chunk.id,
            "page": page,
            "highlight": chunk.highlight,
            "positions": chunk.positions,
        }
        chunks_out.append(
            {
                "chunk_id": chunk.id,
                "knowledge_base_id": meta.get("nk_knowledge_base_id"),
                "source_file_id": meta.get("nk_source_file_id"),
                "file_version_id": meta.get("nk_file_version_id"),
                "document_id": chunk.document_id,
                "file_name": chunk.document_name or chunk.document_keyword,
                "content": chunk.content,
                "similarity": chunk.similarity,
                "weighted_score": item.weighted_score,
                "page": page,
                "positions": chunk.positions,
                "term_similarity": chunk.term_similarity,
                "vector_similarity": chunk.vector_similarity,
                "highlight": chunk.highlight,
                "source_freshness": _compute_source_freshness(source_file),
                "last_synced_at": last_synced_at.isoformat() if last_synced_at else None,
            }
        )
        citation = ChatCitation(
            org_id=member.org_id,
            issued_member_id=member.member_id,
            message_id=None,
            knowledge_base_id=str(meta.get("nk_knowledge_base_id") or ""),
            source_file_id=str(meta.get("nk_source_file_id") or ""),
            file_version_id=str(meta.get("nk_file_version_id") or ""),
            ragflow_document_id=chunk.document_id,
            ragflow_chunk_id=chunk.id,
            page=page,
            positions=chunk.positions,
            score=chunk.similarity,
            quote=(chunk.content or "")[:500],
            evidence_type=evidence_type,
            content=chunk.content,
            source_refs=source_refs,
            runtime_payload=runtime_payload,
            origin=origin,
        )
        db.add(citation)
        await db.flush()
        metrics_service.observe_evidence_returned(evidence_type=evidence_type)
        evidence_out.append(_evidence_response_payload(citation, highlight=chunk.highlight))
    return chunks_out, evidence_out


async def _retrieve_for_set(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowClient,
    *,
    knowledge_set_id: str,
    query: str,
    options: RetrievalOptions | None = None,
    top_k: int | None = None,
    similarity_threshold: float | None = None,
    filters: dict[str, list] | None = None,
    origin: str = RetrievalOrigin.direct_retrieval.value,
    profile_id: str | None = None,
    kbs_override: list | None = None,
    set_items_override: list | None = None,
    bump_set_ids: list[str] | None = None,
) -> dict:
    started = time.perf_counter()
    ks = await knowledge_set_service.get_knowledge_set(db, member, knowledge_set_id)
    if (
        ks.status == KnowledgeSetStatus.disabled.value
        and origin != RetrievalOrigin.evaluation.value
        and kbs_override is None
    ):
        raise ForbiddenError(message="知识集合已禁用", message_key="errors.knowledge.set_disabled")
    if not await has_set_permission(db, member, ks, SetPermission.use.value):
        raise ForbiddenError(message="无权检索该知识集合", message_key="errors.knowledge.retrieval_denied")

    kbs = kbs_override if kbs_override is not None else await knowledge_set_service.list_bound_knowledge_bases(db, member, knowledge_set_id)
    if not kbs:
        raise BadRequestError(message="知识集合未绑定知识库", message_key="errors.knowledge.set_empty")

    from app.services import metadata_service

    normalized_filters = metadata_service.validate_retrieval_filters(
        filters,
        [getattr(kb, "metadata_schema", None) for kb in kbs],
    )

    if profile_id:
        from app.models.retrieval_profile import RetrievalProfile

        profile = await db.get(RetrievalProfile, profile_id)
        if profile is None or profile.deleted_at is not None:
            raise NotFoundError(message="检索配置不存在", message_key="errors.knowledge.profile_not_found")
        allowed_sets = {knowledge_set_id, *(bump_set_ids or [])}
        if profile.knowledge_set_id not in allowed_sets and kbs_override is None:
            raise BadRequestError(
                message="检索配置不属于该知识集合",
                message_key="errors.knowledge.profile_not_found",
            )
        if profile.status not in (
            ProfileStatus.draft.value,
            ProfileStatus.active.value,
            ProfileStatus.archived.value,
        ):
            raise BadRequestError(
                message="检索配置状态不可用",
                message_key="errors.knowledge.profile_not_active",
            )
    else:
        profile = await retrieval_profile_service.get_active_profile(db, knowledge_set_id)
        if profile is None:
            raise BadRequestError(
                message="知识集合缺少生效的检索配置",
                message_key="errors.knowledge.profile_not_active",
            )
    config = merge_profile_config(profile.config)
    effective_top_k = top_k if top_k is not None else int(config.get("top_k", 1024))
    effective_top_n = int(config.get("top_n", 8))
    effective_threshold = similarity_threshold
    if effective_threshold is None:
        effective_threshold = float(config.get("similarity_threshold", 0.2))
    effective_keyword = bool(config.get("keyword", False))
    effective_highlight = bool(config.get("highlight", False))
    failure_policy = str(config.get("failure_policy") or "fail_closed")

    if options:
        if options.top_n is not None:
            effective_top_n = options.top_n
        if options.similarity_threshold is not None:
            effective_threshold = options.similarity_threshold
        if options.keyword is not None:
            effective_keyword = options.keyword
        if options.highlight is not None:
            effective_highlight = options.highlight

    plan_access = await build_access_plan(db, member, kbs)
    if plan_access.kind == AccessPlanKind.no_access or not plan_access.dataset_ids:
        audit = RetrievalAudit(
            member_id=member.member_id,
            org_id=member.org_id,
            knowledge_set_id=knowledge_set_id,
            query_hash=hashlib.sha256(query.encode("utf-8")).hexdigest(),
            candidate_chunk_count=0,
            filtered_chunk_count=0,
            returned_chunk_count=0,
            source_file_ids=[],
            latency_ms=int((time.perf_counter() - started) * 1000),
            status="denied",
            plan_kind=plan_access.kind.value,
            ragflow_call_count=0,
            error_code="errors.knowledge.retrieval_denied",
            origin=origin,
            execution_status="denied",
            successful_slice_count=0,
            failed_slice_count=0,
        )
        db.add(audit)
        await db.commit()
        _observe_retrieval("denied", started)
        raise ForbiddenError(message="无权检索该知识集合", message_key="errors.knowledge.retrieval_denied")

    if normalized_filters:
        plan_access = await metadata_service.apply_metadata_filters_to_access_plan(
            db,
            plan_access,
            normalized_filters,
            kbs,
        )

    set_items = (
        set_items_override
        if set_items_override is not None
        else await knowledge_set_service.list_set_items(db, member, knowledge_set_id)
    )
    metadata_condition = (
        retrieval_planner.build_metadata_condition(normalized_filters)
        if settings.RAGFLOW_METADATA_PUSHDOWN_ENABLED
        else None
    )
    dataset_map = await _dataset_id_by_kb_id(db, kbs)

    build_states: dict[str, str] = {}
    retrieval_states: dict[str, str] = {}
    merged_capabilities: dict = {}
    from app.services import capability_planner, index_state_service
    from app.services.index_registry import list_index_types

    for kb in kbs:
        binding = await runtime_binding_service.get_binding(db, kb.id)
        if binding and binding.capabilities:
            merged_capabilities.update(binding.capabilities)
        for state in await index_state_service.list_states_for_kb(db, kb.id):
            build_states[state.index_type] = state.status
            retrieval_states[state.index_type] = state.retrieval_status

    capability_plan = capability_planner.build_capability_plan(
        query,
        available_indexes=list_index_types(),
        index_states=build_states,
        retrieval_states=retrieval_states,
        capabilities=merged_capabilities,
        force_chunk_only=not settings.KNOWLEDGE_V2_MULTI_INDEX_RETRIEVAL_ENABLED,
    )
    for code in capability_plan.reason_codes:
        metrics_service.observe_capability_plan(reason_code=code)

    plan = retrieval_planner.build_retrieval_plan(
        plan_access,
        kbs,
        set_items,
        metadata_condition=metadata_condition,
        dataset_id_by_kb_id=dataset_map,
    )
    if settings.KNOWLEDGE_V2_MULTI_INDEX_RETRIEVAL_ENABLED:
        plan = retrieval_planner.expand_plan_for_indexes(plan, capability_plan.effective_indexes)
    else:
        primary_index = (
            capability_plan.effective_indexes[0]
            if capability_plan.effective_indexes
            else "chunk"
        )
        for slice_ in plan.slices:
            slice_.index_type = primary_index
    for slice_ in plan.slices:
        slice_.top_k = effective_top_k
        slice_.access_scope = plan_access.kind.value

    if plan_access.kind == AccessPlanKind.no_access or not plan.slices:
        query_id = str(uuid.uuid4())
        latency_ms = int((time.perf_counter() - started) * 1000)
        audit = RetrievalAudit(
            member_id=member.member_id,
            org_id=member.org_id,
            knowledge_set_id=knowledge_set_id,
            query_hash=hashlib.sha256(query.encode("utf-8")).hexdigest(),
            candidate_chunk_count=0,
            filtered_chunk_count=0,
            returned_chunk_count=0,
            source_file_ids=[],
            latency_ms=latency_ms,
            status="ok",
            plan_kind=plan.plan_kind,
            ragflow_call_count=0,
            origin=origin,
            execution_status="empty",
            successful_slice_count=0,
            failed_slice_count=0,
            **_audit_capability_fields(capability_plan),
        )
        db.add(audit)
        for sid in bump_set_ids or [knowledge_set_id]:
            row = await knowledge_set_service.get_knowledge_set(db, member, sid)
            row.usage_count += 1
            row.last_used_at = datetime.now(UTC)
        await db.commit()
        _observe_retrieval("empty", started)
        return {
            "query_id": query_id,
            "chunks": [],
            "evidence": [],
            "status": "empty",
            "diagnostics": {"slice_count": 0},
        }

    merge_result = await retrieval_merge_service.execute_and_merge(
        db,
        ragflow,
        plan,
        allowed_source_file_ids=set(plan_access.source_file_ids),
        query=query,
        top_k=effective_top_k,
        top_n=effective_top_n,
        similarity_threshold=effective_threshold,
        vector_similarity_weight=float(config.get("vector_similarity_weight", 0.7)),
        keyword=effective_keyword,
        highlight=effective_highlight,
        rerank_id=config.get("rerank_id"),
        cross_languages=config.get("cross_languages") or [],
        audit_org_id=member.org_id,
        audit_member_id=member.member_id,
    )

    merged = merge_result.merged
    candidate_count = merge_result.candidate_count
    filtered_count = merge_result.filtered_count
    ragflow_call_count = merge_result.ragflow_call_count
    slice_results = merge_result.slice_results
    successful_slice_count = sum(1 for item in slice_results if item.status == "success")
    failed_slice_count = sum(1 for item in slice_results if item.status == "failed")
    diagnostics = _diagnostics_from_slices(slice_results)
    if merge_result.fallback_used:
        diagnostics["fallback_used"] = True
    if merge_result.deduped_count:
        diagnostics["deduped_count"] = merge_result.deduped_count

    query_id = str(uuid.uuid4())
    latency_ms = int((time.perf_counter() - started) * 1000)
    source_file_ids = sorted(
        {
            item.chunk.document_metadata.get("nk_source_file_id")
            for item in merged
            if item.chunk.document_metadata.get("nk_source_file_id")
        }
    )

    if failed_slice_count > 0 and failure_policy != "degraded":
        audit = RetrievalAudit(
            member_id=member.member_id,
            org_id=member.org_id,
            knowledge_set_id=knowledge_set_id,
            query_hash=hashlib.sha256(query.encode("utf-8")).hexdigest(),
            candidate_chunk_count=candidate_count,
            filtered_chunk_count=filtered_count,
            returned_chunk_count=0,
            source_file_ids=[],
            latency_ms=latency_ms,
            status="error",
            plan_kind=plan.plan_kind,
            ragflow_call_count=ragflow_call_count,
            error_code="errors.knowledge.retrieval_unavailable",
            origin=origin,
            execution_status="failed",
            successful_slice_count=successful_slice_count,
            failed_slice_count=failed_slice_count,
            **_audit_capability_fields(
                capability_plan,
                fallback_used=merge_result.fallback_used,
            ),
        )
        db.add(audit)
        await db.commit()
        _observe_retrieval("failed", started)
        raise ServiceUnavailableError(
            message="知识检索暂时不可用",
            message_key="errors.knowledge.retrieval_unavailable",
            details=diagnostics,
        )

    if failed_slice_count > 0:
        execution_status = "degraded"
    elif not merged:
        execution_status = "empty"
    else:
        execution_status = "success"

    audit = RetrievalAudit(
        member_id=member.member_id,
        org_id=member.org_id,
        knowledge_set_id=knowledge_set_id,
        query_hash=hashlib.sha256(query.encode("utf-8")).hexdigest(),
        candidate_chunk_count=candidate_count,
        filtered_chunk_count=filtered_count,
        returned_chunk_count=len(merged),
        source_file_ids=source_file_ids,
        latency_ms=latency_ms,
        status="ok",
        plan_kind=plan.plan_kind,
        ragflow_call_count=ragflow_call_count,
        error_code="errors.knowledge.retrieval_partial_failure" if failed_slice_count > 0 else None,
        origin=origin,
        execution_status=execution_status,
        successful_slice_count=successful_slice_count,
        failed_slice_count=failed_slice_count,
        **_audit_capability_fields(
            capability_plan,
            fallback_used=merge_result.fallback_used or capability_plan.fallback_used,
        ),
    )
    db.add(audit)
    if origin != RetrievalOrigin.evaluation.value:
        from app.models.knowledge_set import KnowledgeSet

        for sid in bump_set_ids or [knowledge_set_id]:
            row = ks if sid == knowledge_set_id else await db.get(KnowledgeSet, sid)
            if row is not None and row.deleted_at is None:
                row.usage_count += 1
                row.last_used_at = datetime.now(UTC)

    chunks_out, evidence_out = await _persist_retrieval_evidence(
        db,
        member,
        merged,
        origin=origin,
    )
    await db.commit()

    _observe_retrieval(execution_status, started)
    diagnostics["metadata_pushdown"] = bool(getattr(plan, "metadata_pushdown", False))
    payload = {
        "query_id": query_id,
        "chunks": chunks_out,
        "evidence": evidence_out,
        "status": execution_status,
        "diagnostics": diagnostics,
        "latency_ms": latency_ms,
    }
    if (
        settings.KNOWLEDGE_V2_CAPABILITY_PLANNER_ENABLED
        or settings.KNOWLEDGE_V2_MULTI_INDEX_RETRIEVAL_ENABLED
        or origin == RetrievalOrigin.evaluation.value
    ):
        payload["capability_plan"] = capability_plan.to_dict()
        payload["execution_plan"] = {
            "slices": [
                {
                    "index_type": s.index_type,
                    "knowledge_base_id": s.knowledge_base_id,
                    "dataset_id": s.dataset_id,
                    "top_k": s.top_k,
                    "access_scope": s.access_scope,
                }
                for s in plan.slices
            ]
        }
    return payload


def _chunks_to_results(merged: list) -> list[dict]:
    results = []
    for item in merged:
        chunk = item.chunk
        meta = chunk.document_metadata or {}
        results.append(
            {
                "chunk_id": chunk.id,
                "knowledge_base_id": meta.get("nk_knowledge_base_id"),
                "source_file_id": meta.get("nk_source_file_id"),
                "file_version_id": meta.get("nk_file_version_id"),
                "document_id": chunk.document_id,
                "file_name": chunk.document_name or chunk.document_keyword,
                "content": chunk.content,
                "similarity": chunk.similarity,
                "weighted_score": item.weighted_score,
                "page": _extract_page(chunk.positions),
                "positions": chunk.positions,
                "term_similarity": chunk.term_similarity,
                "vector_similarity": chunk.vector_similarity,
                "highlight": chunk.highlight,
            }
        )
    return results


async def _resolve_playground_profile(
    db: AsyncSession,
    knowledge_set_id: str,
    profile_id: str | None,
):
    from app.models.retrieval_profile import RetrievalProfile

    if profile_id:
        profile = await db.get(RetrievalProfile, profile_id)
        if profile is None or profile.deleted_at is not None:
            raise NotFoundError(message="检索配置不存在", message_key="errors.knowledge.profile_not_found")
        if profile.knowledge_set_id != knowledge_set_id:
            raise BadRequestError(
                message="检索配置不属于该知识集合",
                message_key="errors.knowledge.profile_not_found",
            )
        if profile.status not in (ProfileStatus.draft.value, ProfileStatus.active.value):
            raise BadRequestError(
                message="Playground 仅允许 DRAFT 或 ACTIVE 配置",
                message_key="errors.knowledge.profile_not_active",
            )
        return profile
    profile = await retrieval_profile_service.get_active_profile(db, knowledge_set_id)
    if profile is None:
        raise BadRequestError(
            message="知识集合缺少生效的检索配置",
            message_key="errors.knowledge.profile_not_active",
        )
    return profile


# @lat: [[knowledge#Retrieval Playground And Trace]]
async def playground_retrieve(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowClient,
    *,
    knowledge_set_id: str,
    query: str,
    profile_id: str | None = None,
    include_trace: bool = False,
    filters: dict[str, list] | None = None,
) -> dict:
    started = time.perf_counter()
    ks = await knowledge_set_service.get_knowledge_set(db, member, knowledge_set_id)
    if not await has_set_permission(db, member, ks, SetPermission.manage.value):
        raise ForbiddenError(message="无权使用检索调试台", message_key="errors.knowledge.retrieval_denied")

    kbs = await knowledge_set_service.list_bound_knowledge_bases(db, member, knowledge_set_id)
    if not kbs:
        raise BadRequestError(message="知识集合未绑定知识库", message_key="errors.knowledge.set_empty")

    from app.services import metadata_service

    normalized_filters = metadata_service.validate_retrieval_filters(
        filters,
        [getattr(kb, "metadata_schema", None) for kb in kbs],
    )

    profile = await _resolve_playground_profile(db, knowledge_set_id, profile_id)
    config = merge_profile_config(profile.config)
    effective_top_k = int(config.get("top_k", 1024))
    effective_top_n = int(config.get("top_n", 8))
    effective_threshold = float(config.get("similarity_threshold", 0.2))
    effective_keyword = bool(config.get("keyword", False))
    effective_highlight = bool(config.get("highlight", False))

    acl_started = time.perf_counter()
    plan_access = await build_access_plan(db, member, kbs)
    if normalized_filters and plan_access.kind != AccessPlanKind.no_access and plan_access.dataset_ids:
        plan_access = await metadata_service.apply_metadata_filters_to_access_plan(
            db,
            plan_access,
            normalized_filters,
            kbs,
        )
    set_items = await knowledge_set_service.list_set_items(db, member, knowledge_set_id)
    metadata_condition = (
        retrieval_planner.build_metadata_condition(normalized_filters)
        if settings.RAGFLOW_METADATA_PUSHDOWN_ENABLED
        else None
    )
    dataset_map = await _dataset_id_by_kb_id(db, kbs)
    plan = retrieval_planner.build_retrieval_plan(
        plan_access,
        kbs,
        set_items,
        metadata_condition=metadata_condition,
        dataset_id_by_kb_id=dataset_map,
    )
    acl_ms = int((time.perf_counter() - acl_started) * 1000)

    plan_out = {
        "knowledge_bases": len({kb.id for kb in kbs}),
        "slices": len(plan.slices),
    }
    empty_timing = {
        "acl_ms": acl_ms,
        "ragflow_ms": 0,
        "security_ms": 0,
        "merge_ms": 0,
        "total_ms": int((time.perf_counter() - started) * 1000),
    }
    empty_summary = retrieval_trace_service.build_filter_summary(
        candidates=0,
        filter_counts=None,
        returned=0,
    )

    if plan_access.kind == AccessPlanKind.no_access or not plan.slices:
        latency_ms = empty_timing["total_ms"]
        if include_trace:
            await retrieval_trace_service.persist_trace(
                db,
                member,
                query_hash=hashlib.sha256(query.encode("utf-8")).hexdigest(),
                knowledge_set_id=knowledge_set_id,
                profile_id=profile.id,
                profile_version=profile.version,
                slice_results=[],
                timing=empty_timing,
                filter_summary=empty_summary,
                chunk_traces=[],
                latency_ms=latency_ms,
            )
            await db.commit()
        return {
            "query": query,
            "plan": plan_out,
            "timing": empty_timing,
            "results": [],
            "filter_summary": empty_summary,
        }

    merge_result = await retrieval_merge_service.execute_and_merge(
        db,
        ragflow,
        plan,
        allowed_source_file_ids=set(plan_access.source_file_ids),
        query=query,
        top_k=effective_top_k,
        top_n=effective_top_n,
        similarity_threshold=effective_threshold,
        vector_similarity_weight=float(config.get("vector_similarity_weight", 0.7)),
        keyword=effective_keyword,
        highlight=effective_highlight,
        rerank_id=config.get("rerank_id"),
        cross_languages=config.get("cross_languages") or [],
        audit_org_id=member.org_id,
        audit_member_id=member.member_id,
    )

    merge_timing = merge_result.timing
    timing = {
        "acl_ms": acl_ms,
        "ragflow_ms": int(getattr(merge_timing, "ragflow_ms", 0) or 0),
        "security_ms": int(getattr(merge_timing, "security_ms", 0) or 0),
        "merge_ms": int(getattr(merge_timing, "merge_ms", 0) or 0),
        "total_ms": int((time.perf_counter() - started) * 1000),
    }
    filter_summary = retrieval_trace_service.build_filter_summary(
        candidates=merge_result.candidate_count,
        filter_counts=merge_result.filter_counts,
        returned=len(merge_result.merged),
    )
    results = _chunks_to_results(merge_result.merged)

    if include_trace:
        await retrieval_trace_service.persist_trace(
            db,
            member,
            query_hash=hashlib.sha256(query.encode("utf-8")).hexdigest(),
            knowledge_set_id=knowledge_set_id,
            profile_id=profile.id,
            profile_version=profile.version,
            slice_results=retrieval_trace_service.build_slice_results_summary(merge_result.slice_results),
            timing=timing,
            filter_summary=filter_summary,
            chunk_traces=retrieval_trace_service.build_chunk_traces(
                merged=merge_result.merged,
                dropped_chunks=merge_result.dropped_chunks,
            ),
            latency_ms=timing["total_ms"],
        )
        await db.commit()

    return {
        "query": query,
        "plan": plan_out,
        "timing": timing,
        "results": results,
        "filter_summary": filter_summary,
    }

"""Secure retrieval pipeline with planner and merge."""

from __future__ import annotations

import hashlib
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ForbiddenError
from app.integrations.ragflow.client import RagflowClient
from app.models.enums import AccessPlanKind, DEFAULT_RETRIEVAL_CONFIG, SetPermission
from app.models.retrieval_audit import RetrievalAudit
from app.schemas.knowledge import RetrievalOptions
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_set_service, retrieval_merge_service, retrieval_planner
from app.services.permission_service import build_access_plan, has_set_permission


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
) -> dict:
    started = time.perf_counter()
    ks = await knowledge_set_service.get_knowledge_set(db, member, knowledge_set_id)
    if not await has_set_permission(db, member, ks, SetPermission.use.value):
        raise ForbiddenError(message="无权检索该知识集合", message_key="errors.knowledge.retrieval_denied")

    kbs = await knowledge_set_service.list_bound_knowledge_bases(db, member, knowledge_set_id)
    if not kbs:
        raise BadRequestError(message="知识集合未绑定知识库", message_key="errors.knowledge.set_empty")

    config = dict(ks.retrieval_config or DEFAULT_RETRIEVAL_CONFIG)
    effective_top_k = top_k if top_k is not None else int(config.get("top_k", 1024))
    effective_top_n = int(config.get("top_n", 8))
    effective_threshold = similarity_threshold
    if effective_threshold is None:
        effective_threshold = float(config.get("similarity_threshold", 0.2))
    effective_keyword = bool(config.get("keyword", False))
    effective_highlight = bool(config.get("highlight", False))

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
        )
        db.add(audit)
        await db.commit()
        raise ForbiddenError(message="无权检索该知识集合", message_key="errors.knowledge.retrieval_denied")

    set_items = await knowledge_set_service.list_set_items(db, member, knowledge_set_id)
    kb_weights = {item.knowledge_base_id: float(item.weight) for item in set_items}
    plan = retrieval_planner.build_retrieval_plan(plan_access, kbs, kb_weights=kb_weights)

    if not plan.slices:
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
        )
        db.add(audit)
        ks.usage_count += 1
        ks.last_used_at = datetime.now(UTC)
        await db.commit()
        return {"query_id": query_id, "chunks": []}

    merged, candidate_count, filtered_count, ragflow_call_count = await retrieval_merge_service.execute_and_merge(
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
    )

    query_id = str(uuid.uuid4())
    latency_ms = int((time.perf_counter() - started) * 1000)
    source_file_ids = sorted(
        {
            item.chunk.document_metadata.get("nk_source_file_id")
            for item in merged
            if item.chunk.document_metadata.get("nk_source_file_id")
        }
    )
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
    )
    db.add(audit)
    ks.usage_count += 1
    ks.last_used_at = datetime.now(UTC)
    await db.commit()

    chunks_out = []
    for item in merged:
        chunk = item.chunk
        meta = chunk.document_metadata or {}
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
                "page": _extract_page(chunk.positions),
                "positions": chunk.positions,
                "term_similarity": chunk.term_similarity,
                "vector_similarity": chunk.vector_similarity,
                "highlight": chunk.highlight,
            }
        )

    return {"query_id": query_id, "chunks": chunks_out}

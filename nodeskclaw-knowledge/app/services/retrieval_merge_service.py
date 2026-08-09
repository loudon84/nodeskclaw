"""Parallel retrieval execution, merge, dedupe and rank."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException
from app.integrations.ragflow.client import RagflowClient
from app.integrations.ragflow.models import RagflowChunk
from app.models.enums import RetrievalSliceKind
from app.services import chunk_security_service
from app.services.retrieval_planner import RetrievalPlan, RetrievalSlice

logger = logging.getLogger(__name__)


@dataclass
class RetrievalSliceResult:
    knowledge_base_id: str | None
    dataset_id: str
    status: str
    latency_ms: int
    candidate_count: int
    safe_count: int
    error_code: str | None = None


@dataclass
class MergedChunk:
    chunk: RagflowChunk
    weighted_score: float
    weight: float


@dataclass
class MergeTiming:
    ragflow_ms: int = 0
    security_ms: int = 0
    merge_ms: int = 0


@dataclass
class MergeExecutionResult:
    merged: list[MergedChunk]
    candidate_count: int
    filtered_count: int
    ragflow_call_count: int
    slice_results: list[RetrievalSliceResult]
    timing: MergeTiming | None = None
    filter_counts: dict[str, int] | None = None
    dropped_chunks: list[tuple] | None = None


def _slice_error_code(exc: BaseException) -> str:
    if isinstance(exc, AppException) and exc.message_key:
        return exc.message_key
    return "errors.knowledge.retrieval_partial_failure"


async def _retrieve_slice(
    ragflow: RagflowClient,
    slice_: RetrievalSlice,
    *,
    query: str,
    top_k: int,
    similarity_threshold: float | None,
    vector_similarity_weight: float | None,
    keyword: bool,
    highlight: bool,
    rerank_id: str | None,
    cross_languages: list[str] | None,
    semaphore: asyncio.Semaphore,
) -> tuple[RetrievalSliceResult, list[RagflowChunk]]:
    started = time.perf_counter()
    async with semaphore:
        document_ids = slice_.document_ids if slice_.kind == RetrievalSliceKind.filtered_documents else None
        metadata_condition = slice_.metadata_condition
        try:
            result = await ragflow.retrieve(
                question=query,
                dataset_ids=[slice_.dataset_id],
                document_ids=document_ids,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                vector_similarity_weight=vector_similarity_weight,
                keyword=keyword,
                highlight=highlight,
                rerank_id=rerank_id,
                cross_languages=cross_languages,
                metadata_condition=metadata_condition,
            )
            chunks = result.chunks
            return (
                RetrievalSliceResult(
                    knowledge_base_id=slice_.knowledge_base_id,
                    dataset_id=slice_.dataset_id,
                    status="success",
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    candidate_count=len(chunks),
                    safe_count=0,
                    error_code=None,
                ),
                chunks,
            )
        except Exception as exc:
            failure = exc
            # Metadata pushdown is optimization only; fall back to ACL document_ids.
            if metadata_condition:
                try:
                    result = await ragflow.retrieve(
                        question=query,
                        dataset_ids=[slice_.dataset_id],
                        document_ids=document_ids,
                        top_k=top_k,
                        similarity_threshold=similarity_threshold,
                        vector_similarity_weight=vector_similarity_weight,
                        keyword=keyword,
                        highlight=highlight,
                        rerank_id=rerank_id,
                        cross_languages=cross_languages,
                        metadata_condition=None,
                    )
                    chunks = result.chunks
                    return (
                        RetrievalSliceResult(
                            knowledge_base_id=slice_.knowledge_base_id,
                            dataset_id=slice_.dataset_id,
                            status="success",
                            latency_ms=int((time.perf_counter() - started) * 1000),
                            candidate_count=len(chunks),
                            safe_count=0,
                            error_code=None,
                        ),
                        chunks,
                    )
                except Exception as retry_exc:
                    failure = retry_exc
            logger.warning(
                "retrieval slice failed dataset_id=%s knowledge_base_id=%s: %s",
                slice_.dataset_id,
                slice_.knowledge_base_id,
                failure,
            )
            return (
                RetrievalSliceResult(
                    knowledge_base_id=slice_.knowledge_base_id,
                    dataset_id=slice_.dataset_id,
                    status="failed",
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    candidate_count=0,
                    safe_count=0,
                    error_code=_slice_error_code(failure),
                ),
                [],
            )


def _safe_count_for_slice(slice_: RetrievalSlice, safe_chunks: list[RagflowChunk]) -> int:
    if slice_.kind == RetrievalSliceKind.filtered_documents:
        allowed = set(slice_.document_ids)
        return sum(1 for chunk in safe_chunks if chunk.document_id in allowed)
    return sum(
        1
        for chunk in safe_chunks
        if (chunk.dataset_id or chunk.kb_id or "") == slice_.dataset_id
    )


async def execute_and_merge(
    db: AsyncSession,
    ragflow: RagflowClient,
    plan: RetrievalPlan,
    *,
    allowed_source_file_ids: set[str],
    query: str,
    top_k: int,
    top_n: int,
    similarity_threshold: float | None,
    vector_similarity_weight: float | None,
    keyword: bool,
    highlight: bool,
    rerank_id: str | None,
    cross_languages: list[str] | None,
    audit_org_id: str | None = None,
    audit_member_id: str | None = None,
) -> MergeExecutionResult:
    empty_timing = MergeTiming()
    empty_counts = {
        "unauthorized": 0,
        "superseded": 0,
        "metadata_mismatch": 0,
        "unknown": 0,
    }
    if not plan.slices:
        return MergeExecutionResult(
            merged=[],
            candidate_count=0,
            filtered_count=0,
            ragflow_call_count=0,
            slice_results=[],
            timing=empty_timing,
            filter_counts=empty_counts,
            dropped_chunks=[],
        )

    semaphore = asyncio.Semaphore(max(1, int(settings.RETRIEVAL_MAX_PARALLEL_SLICES)))
    ragflow_started = time.perf_counter()
    tasks = [
        _retrieve_slice(
            ragflow,
            slice_,
            query=query,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            vector_similarity_weight=vector_similarity_weight,
            keyword=keyword,
            highlight=highlight,
            rerank_id=rerank_id,
            cross_languages=cross_languages,
            semaphore=semaphore,
        )
        for slice_ in plan.slices
    ]
    results = await asyncio.gather(*tasks)
    ragflow_ms = int((time.perf_counter() - ragflow_started) * 1000)

    slice_results: list[RetrievalSliceResult] = []
    candidate_chunks: list[RagflowChunk] = []
    ragflow_call_count = 0
    for (slice_result, chunks), slice_ in zip(results, plan.slices, strict=True):
        slice_results.append(slice_result)
        if slice_result.status == "success":
            ragflow_call_count += 1
            candidate_chunks.extend(chunks)

    candidate_count = len(candidate_chunks)
    security_started = time.perf_counter()
    clean_result = await chunk_security_service.clean_chunks(
        db,
        ragflow,
        candidate_chunks,
        allowed_source_file_ids=allowed_source_file_ids,
        audit_org_id=audit_org_id,
        audit_member_id=audit_member_id,
    )
    security_ms = int((time.perf_counter() - security_started) * 1000)
    safe_chunks = clean_result.safe_chunks
    filtered_count = clean_result.filtered_count

    for index, slice_ in enumerate(plan.slices):
        if slice_results[index].status == "success":
            slice_results[index].safe_count = _safe_count_for_slice(slice_, safe_chunks)

    merge_started = time.perf_counter()
    deduped: dict[tuple[str, str], MergedChunk] = {}
    slice_weight_by_dataset: dict[str, float] = {s.dataset_id: s.weight for s in plan.slices}
    for chunk in safe_chunks:
        dataset_id = chunk.dataset_id or chunk.kb_id or ""
        weight = slice_weight_by_dataset.get(dataset_id, 1.0)
        weighted_score = float(chunk.similarity) * weight
        key = (chunk.id, chunk.document_id)
        existing = deduped.get(key)
        if existing is None or weighted_score > existing.weighted_score:
            deduped[key] = MergedChunk(chunk=chunk, weighted_score=weighted_score, weight=weight)

    ranked = sorted(deduped.values(), key=lambda item: item.weighted_score, reverse=True)[:top_n]
    merge_ms = int((time.perf_counter() - merge_started) * 1000)
    return MergeExecutionResult(
        merged=ranked,
        candidate_count=candidate_count,
        filtered_count=filtered_count,
        ragflow_call_count=ragflow_call_count,
        slice_results=slice_results,
        timing=MergeTiming(ragflow_ms=ragflow_ms, security_ms=security_ms, merge_ms=merge_ms),
        filter_counts=clean_result.filter_counts(),
        dropped_chunks=list(clean_result.dropped),
    )

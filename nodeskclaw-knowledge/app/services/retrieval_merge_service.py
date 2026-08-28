"""Parallel retrieval execution, merge, dedupe and rank."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.runtime.ragflow import RagflowRuntimeAdapter
from app.core.exceptions import AppException
from app.integrations.ragflow.models import RagflowChunk
from app.models.enums import RuntimeRetrievalMode
from app.services import chunk_security_service
from app.services.retrieval_planner import RetrievalPlan, RuntimeExecutionSlice

logger = logging.getLogger(__name__)

MODE_TO_PROVIDER: dict[str, str] = {
    "semantic": "semantic",
    "graph_assisted": "ragflow_graph",
    "compiled_assisted": "ragflow_compilation",
    "toc_enhanced": "ragflow_toc",
}


def mode_to_provider(mode: str) -> str:
    return MODE_TO_PROVIDER.get(mode, mode)


@dataclass
class RetrievalSliceResult:
    knowledge_base_id: str | None
    dataset_id: str
    status: str
    latency_ms: int
    candidate_count: int
    safe_count: int
    error_code: str | None = None
    runtime_mode: str = RuntimeRetrievalMode.semantic.value
    access_scope: str = "full"
    fallback_used: bool = False
    fallback_reason: str | None = None
    aggregate_security_fallback: bool = False


@dataclass
class MergedChunk:
    chunk: RagflowChunk
    weighted_score: float
    weight: float
    slice_mode: str = RuntimeRetrievalMode.semantic.value


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
    fallback_used: bool = False
    deduped_count: int = 0
    fusion: dict[str, Any] | None = None


RRF_K = 60


def _rank_by_weighted_similarity(
    safe_chunks: list[tuple[RagflowChunk, str]],
    slice_weight_by_dataset: dict[str, float],
) -> list[MergedChunk]:
    deduped: dict[tuple, MergedChunk] = {}
    for chunk, slice_mode in safe_chunks:
        dataset_id = chunk.dataset_id or chunk.kb_id or ""
        weight = slice_weight_by_dataset.get(dataset_id, 1.0)
        weighted_score = float(chunk.similarity) * weight
        key = _dedup_key(chunk)
        existing = deduped.get(key)
        if existing is None or weighted_score > existing.weighted_score:
            deduped[key] = MergedChunk(
                chunk=chunk,
                weighted_score=weighted_score,
                weight=weight,
                slice_mode=slice_mode,
            )
    return sorted(deduped.values(), key=lambda item: item.weighted_score, reverse=True)


def _rank_by_rrf(
    safe_chunks: list[tuple[RagflowChunk, str]],
    slice_weight_by_dataset: dict[str, float],
) -> tuple[list[MergedChunk], dict[str, Any]]:
    by_provider: dict[str, list[MergedChunk]] = {}
    for chunk, provider in safe_chunks:
        dataset_id = chunk.dataset_id or chunk.kb_id or ""
        weight = slice_weight_by_dataset.get(dataset_id, 1.0)
        meta = chunk.document_metadata or {}
        provider_weight = float(meta.get("nk_provider_weight") or weight)
        weighted_score = float(chunk.similarity) * provider_weight
        provider_key = provider or "semantic"
        by_provider.setdefault(provider_key, []).append(
            MergedChunk(
                chunk=chunk,
                weighted_score=weighted_score,
                weight=provider_weight,
                slice_mode=provider_key,
            )
        )

    scores: dict[tuple, float] = {}
    chunk_map: dict[tuple, MergedChunk] = {}
    for provider, items in by_provider.items():
        provider_weight = max(item.weight for item in items) if items else 1.0
        ranked = sorted(items, key=lambda item: item.weighted_score, reverse=True)
        for rank, item in enumerate(ranked, start=1):
            key = _dedup_key(item.chunk)
            scores[key] = scores.get(key, 0.0) + provider_weight / (RRF_K + rank)
            chunk_map[key] = item

    merged = sorted(
        (
            MergedChunk(
                chunk=chunk_map[key].chunk,
                weighted_score=score,
                weight=chunk_map[key].weight,
                slice_mode=chunk_map[key].slice_mode,
            )
            for key, score in scores.items()
        ),
        key=lambda item: item.weighted_score,
        reverse=True,
    )
    return merged, {
        "strategy": "weighted_rrf",
        "k": RRF_K,
        "provider_count": len(by_provider),
    }


def _normalize_content(text: str | None) -> str:
    return " ".join((text or "").split()).lower()


def _dedup_key(chunk: RagflowChunk) -> tuple:
    meta = chunk.document_metadata or {}
    page = None
    for pos in chunk.positions or []:
        if isinstance(pos, (list, tuple)) and len(pos) >= 1:
            page = pos[0]
            break
    lineage = meta.get("nk_lineage_id") or chunk.id
    return (
        meta.get("nk_source_file_id"),
        meta.get("nk_file_version_id"),
        page,
        lineage,
    )


def _apply_aggregate_gate(slice_: RuntimeExecutionSlice) -> tuple[RuntimeExecutionSlice, bool]:
    """Enforce filtered access_scope gate; fallback aggregate modes to semantic."""
    if slice_.access_scope != "filtered":
        return slice_, False

    needs_fallback = (
        slice_.use_kg
        or slice_.include_knowledge_compilation
        or slice_.mode
        in {
            RuntimeRetrievalMode.graph_assisted,
            RuntimeRetrievalMode.compiled_assisted,
        }
    )
    if not needs_fallback:
        return slice_, False

    return (
        RuntimeExecutionSlice(
            knowledge_base_id=slice_.knowledge_base_id,
            dataset_id=slice_.dataset_id,
            document_ids=slice_.document_ids,
            access_scope=slice_.access_scope,
            mode=RuntimeRetrievalMode.semantic,
            retrieval_features=list(slice_.retrieval_features),
            use_kg=False,
            include_knowledge_compilation=False,
            toc_enhance=slice_.toc_enhance,
            top_k=slice_.top_k,
            weight=slice_.weight,
            fallback_mode=slice_.fallback_mode,
            metadata_condition=slice_.metadata_condition,
            provider=slice_.provider,
        ),
        True,
    )


def _slice_error_code(exc: BaseException) -> str:
    if isinstance(exc, AppException) and exc.message_key:
        return exc.message_key
    return "errors.knowledge.retrieval_partial_failure"


async def _retrieve_slice(
    ragflow: RagflowRuntimeAdapter,
    slice_: RuntimeExecutionSlice,
    *,
    query: str,
    top_k: int,
    similarity_threshold: float | None,
    vector_similarity_weight: float | None,
    keyword: bool,
    highlight: bool,
    rerank_id: str | None,
    cross_languages: list[str] | None,
    rerank_candidates_count: int | None,
    semaphore: asyncio.Semaphore,
) -> tuple[RetrievalSliceResult, list[RagflowChunk]]:
    started = time.perf_counter()
    gated_slice, aggregate_fallback = _apply_aggregate_gate(slice_)
    runtime_mode = gated_slice.mode.value

    async def _call_retrieve(*, metadata_condition) -> list[RagflowChunk]:
        result = await ragflow.retrieve(
            question=query,
            dataset_ids=[gated_slice.dataset_id],
            document_ids=gated_slice.document_ids,
            top_k=gated_slice.top_k or top_k,
            similarity_threshold=similarity_threshold,
            vector_similarity_weight=vector_similarity_weight,
            keyword=keyword,
            highlight=highlight,
            rerank_id=rerank_id,
            cross_languages=cross_languages,
            metadata_condition=metadata_condition,
            use_kg=gated_slice.use_kg or None,
            toc_enhance=gated_slice.toc_enhance or None,
            include_knowledge_compilation=gated_slice.include_knowledge_compilation or None,
            rerank_candidates_count=rerank_candidates_count,
        )
        return list(result.chunks)

    async with semaphore:
        metadata_condition = gated_slice.metadata_condition
        fallback_used = aggregate_fallback
        fallback_reason: str | None = "aggregate_security_fallback" if aggregate_fallback else None
        failure: BaseException | None = None
        chunks: list[RagflowChunk] = []

        try:
            chunks = await _call_retrieve(metadata_condition=metadata_condition)
        except Exception as exc:
            failure = exc
            if metadata_condition:
                try:
                    chunks = await _call_retrieve(metadata_condition=None)
                    failure = None
                except Exception as retry_exc:
                    failure = retry_exc

        if failure is not None and runtime_mode != RuntimeRetrievalMode.semantic.value:
            try:
                gated_slice = RuntimeExecutionSlice(
                    knowledge_base_id=gated_slice.knowledge_base_id,
                    dataset_id=gated_slice.dataset_id,
                    document_ids=gated_slice.document_ids,
                    access_scope=gated_slice.access_scope,
                    mode=RuntimeRetrievalMode.semantic,
                    retrieval_features=list(gated_slice.retrieval_features),
                    use_kg=False,
                    include_knowledge_compilation=False,
                    toc_enhance=False,
                    top_k=gated_slice.top_k,
                    weight=gated_slice.weight,
                    fallback_mode=gated_slice.fallback_mode,
                    metadata_condition=None,
                    provider=gated_slice.provider,
                )
                runtime_mode = RuntimeRetrievalMode.semantic.value
                chunks = await _call_retrieve(metadata_condition=None)
                fallback_used = True
                fallback_reason = _slice_error_code(failure)
                failure = None
            except Exception as fallback_exc:
                failure = fallback_exc

        if failure is not None:
            logger.warning(
                "retrieval slice failed dataset_id=%s knowledge_base_id=%s mode=%s: %s",
                slice_.dataset_id,
                slice_.knowledge_base_id,
                runtime_mode,
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
                    runtime_mode=runtime_mode,
                    access_scope=slice_.access_scope,
                    fallback_used=fallback_used,
                    fallback_reason=fallback_reason,
                    aggregate_security_fallback=aggregate_fallback,
                ),
                [],
            )

        return (
            RetrievalSliceResult(
                knowledge_base_id=slice_.knowledge_base_id,
                dataset_id=slice_.dataset_id,
                status="success",
                latency_ms=int((time.perf_counter() - started) * 1000),
                candidate_count=len(chunks),
                safe_count=0,
                error_code=None,
                runtime_mode=runtime_mode,
                access_scope=slice_.access_scope,
                fallback_used=fallback_used,
                fallback_reason=fallback_reason,
                aggregate_security_fallback=aggregate_fallback,
            ),
            chunks,
        )


def _safe_count_for_slice(slice_: RuntimeExecutionSlice, safe_chunks: list[RagflowChunk]) -> int:
    if slice_.access_scope == "filtered" and slice_.document_ids is not None:
        allowed = set(slice_.document_ids)
        return sum(1 for chunk in safe_chunks if chunk.document_id in allowed)
    return sum(
        1
        for chunk in safe_chunks
        if (chunk.dataset_id or chunk.kb_id or "") == slice_.dataset_id
    )


async def execute_and_merge(
    db: AsyncSession,
    ragflow: RagflowRuntimeAdapter,
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
    rerank_candidates_count: int | None = None,
    federation_plan=None,
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
            rerank_candidates_count=rerank_candidates_count,
            semaphore=semaphore,
        )
        for slice_ in plan.slices
    ]
    results = await asyncio.gather(*tasks)
    ragflow_ms = int((time.perf_counter() - ragflow_started) * 1000)

    slice_results: list[RetrievalSliceResult] = []
    candidate_chunks: list[tuple[RagflowChunk, str]] = []
    ragflow_call_count = 0
    for (slice_result, chunks), slice_ in zip(results, plan.slices, strict=True):
        slice_results.append(slice_result)
        if slice_result.status == "success":
            ragflow_call_count += 1
            mode = slice_result.runtime_mode
            provider = slice_.provider or mode_to_provider(mode)
            for chunk in chunks:
                candidate_chunks.append((chunk, provider))

    if federation_plan is not None:
        artifact_chunks = await _retrieve_artifact_provider_candidates(
            db,
            ragflow,
            federation_plan,
            query=query,
            allowed_source_file_ids=allowed_source_file_ids,
        )
        candidate_chunks.extend(artifact_chunks)
        if artifact_chunks:
            ragflow_call_count += 1

    candidate_count = len(candidate_chunks)
    security_started = time.perf_counter()
    clean_result = await chunk_security_service.clean_chunks_with_modes(
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

    slice_weight_by_dataset: dict[str, float] = {s.dataset_id: s.weight for s in plan.slices}
    merge_started = time.perf_counter()
    dedup_before = len(safe_chunks)
    if settings.KNOWLEDGE_V23_RRF_FUSION_ENABLED:
        ranked_all, fusion = _rank_by_rrf(clean_result.chunk_modes, slice_weight_by_dataset)
        ranked = ranked_all[:top_n]
    else:
        fusion = {"strategy": "weighted_similarity"}
        ranked_all = _rank_by_weighted_similarity(clean_result.chunk_modes, slice_weight_by_dataset)
        ranked = ranked_all[:top_n]
    deduped_count = max(0, dedup_before - len(ranked_all))
    merge_ms = int((time.perf_counter() - merge_started) * 1000)
    any_fallback = any(r.fallback_used for r in slice_results)
    return MergeExecutionResult(
        merged=ranked,
        candidate_count=candidate_count,
        filtered_count=filtered_count,
        ragflow_call_count=ragflow_call_count,
        slice_results=slice_results,
        timing=MergeTiming(ragflow_ms=ragflow_ms, security_ms=security_ms, merge_ms=merge_ms),
        filter_counts=clean_result.filter_counts(),
        dropped_chunks=list(clean_result.dropped),
        fallback_used=any_fallback,
        deduped_count=deduped_count,
        fusion=fusion,
    )


async def _retrieve_artifact_provider_candidates(
    db: AsyncSession,
    ragflow: RagflowRuntimeAdapter,
    federation_plan,
    *,
    query: str,
    allowed_source_file_ids: set[str],
) -> list[tuple[RagflowChunk, str]]:
    from app.knowledge_artifacts.base import ArtifactBuildContext, ArtifactEvidenceCandidate
    from app.knowledge_artifacts.registry import ensure_default_providers, get_provider
    from app.models.knowledge_base import KnowledgeBase
    from app.services import build_input_manifest_service, runtime_binding_service

    artifact_providers = [
        item
        for item in federation_plan.providers
        if str(item.provider).startswith("artifact_")
    ]
    if not artifact_providers:
        return []

    ensure_default_providers()
    out: list[tuple[RagflowChunk, str]] = []
    seen_kb: set[str] = set()

    for entry in artifact_providers:
        if entry.knowledge_base_id in seen_kb:
            continue
        seen_kb.add(entry.knowledge_base_id)
        artifact_type = entry.provider.removeprefix("artifact_")
        provider = get_provider(artifact_type)
        if provider is None:
            continue
        kb = await db.get(KnowledgeBase, entry.knowledge_base_id)
        if kb is None or kb.deleted_at is not None:
            continue
        manifest_hash, _, manifest_summary = await build_input_manifest_service.compute_manifest(db, kb)
        dataset_id = await runtime_binding_service.get_dataset_id(db, kb)
        if not dataset_id:
            continue
        context = ArtifactBuildContext(
            org_id=kb.org_id,
            knowledge_base_id=kb.id,
            dataset_id=dataset_id,
            adapter=ragflow,
            manifest_hash=manifest_hash,
            manifest_summary=manifest_summary,
        )
        hits: list[ArtifactEvidenceCandidate] = await provider.retrieve(query, context)
        for rank, hit in enumerate(hits, start=1):
            if not hit.citable:
                continue
            if hit.source_refs and not all(
                ref.source_file_id in allowed_source_file_ids for ref in hit.source_refs
            ):
                continue
            provider_name = entry.provider
            first_ref = hit.source_refs[0] if hit.source_refs else None
            chunk = RagflowChunk(
                id=f"artifact:{artifact_type}:{hit.provider_payload.get('node_id') or rank}",
                content=hit.content,
                similarity=float(hit.provider_score or 0.5),
                document_metadata={
                    "nk_source_file_id": first_ref.source_file_id if first_ref else None,
                    "nk_file_version_id": first_ref.file_version_id if first_ref else None,
                    "nk_knowledge_base_id": kb.id,
                    "nk_evidence_type": artifact_type,
                    "nk_provider_weight": hit.provider_weight or entry.weight,
                    "nk_lineage_id": f"{artifact_type}:{hit.title}",
                },
            )
            out.append((chunk, provider_name))
    return out

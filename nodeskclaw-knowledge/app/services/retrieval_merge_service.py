"""Parallel retrieval execution, merge, dedupe and rank."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.ragflow.client import RagflowClient
from app.integrations.ragflow.models import RagflowChunk
from app.models.enums import RetrievalSliceKind
from app.services import chunk_security_service
from app.services.retrieval_planner import RetrievalPlan, RetrievalSlice


@dataclass
class MergedChunk:
    chunk: RagflowChunk
    weighted_score: float
    weight: float


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
) -> tuple[RetrievalSlice, list[RagflowChunk]]:
    document_ids = slice_.document_ids if slice_.kind == RetrievalSliceKind.filtered_documents else None
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
    )
    return slice_, result.chunks


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
) -> tuple[list[MergedChunk], int, int, int]:
    if not plan.slices:
        return [], 0, 0, 0

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
        )
        for slice_ in plan.slices
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    candidate_chunks: list[RagflowChunk] = []
    ragflow_call_count = 0
    for item in results:
        if isinstance(item, Exception):
            continue
        _slice, chunks = item
        ragflow_call_count += 1
        candidate_chunks.extend(chunks)

    candidate_count = len(candidate_chunks)
    safe_chunks, filtered_count = await chunk_security_service.clean_chunks(
        db,
        ragflow,
        candidate_chunks,
        allowed_source_file_ids=allowed_source_file_ids,
    )

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
    return ranked, candidate_count, filtered_count, ragflow_call_count

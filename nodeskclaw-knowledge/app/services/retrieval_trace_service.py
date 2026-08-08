"""Persist retrieval playground traces without default full-text logging."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.retrieval_trace import RetrievalTrace
from app.schemas.principal import KnowledgePrincipal


_CONTENT_PREVIEW_CHARS = 200


def build_filter_summary(
    *,
    candidates: int,
    filter_counts: dict[str, int] | None,
    returned: int,
) -> dict[str, int]:
    counts = filter_counts or {}
    return {
        "candidates": candidates,
        "unauthorized": int(counts.get("unauthorized", 0)),
        "superseded": int(counts.get("superseded", 0)),
        "metadata_mismatch": int(counts.get("metadata_mismatch", 0)),
        "returned": returned,
    }


def build_slice_results_summary(slice_results: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "knowledge_base_id": getattr(item, "knowledge_base_id", None),
            "dataset_id": getattr(item, "dataset_id", None),
            "status": getattr(item, "status", None),
            "latency_ms": getattr(item, "latency_ms", 0),
            "candidate_count": getattr(item, "candidate_count", 0),
            "safe_count": getattr(item, "safe_count", 0),
            "error_code": getattr(item, "error_code", None),
        }
        for item in slice_results
    ]


def build_chunk_traces(
    *,
    merged: list[Any],
    dropped_chunks: list[tuple] | None = None,
) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    include_content = bool(settings.DEBUG_CONTENT_LOGGING)
    for item in merged:
        chunk = getattr(item, "chunk", item)
        meta = getattr(chunk, "document_metadata", None) or {}
        entry: dict[str, Any] = {
            "chunk_id": getattr(chunk, "id", None),
            "document_id": getattr(chunk, "document_id", None),
            "source_file_id": meta.get("nk_source_file_id"),
            "similarity": float(getattr(chunk, "similarity", 0.0) or 0.0),
            "weighted_score": float(getattr(item, "weighted_score", getattr(chunk, "similarity", 0.0)) or 0.0),
            "filter_reason": None,
        }
        if include_content:
            content = getattr(chunk, "content", None) or ""
            entry["content"] = content[:_CONTENT_PREVIEW_CHARS]
        traces.append(entry)

    for chunk, reason in dropped_chunks or []:
        meta = getattr(chunk, "document_metadata", None) or {}
        entry = {
            "chunk_id": getattr(chunk, "id", None),
            "document_id": getattr(chunk, "document_id", None),
            "source_file_id": meta.get("nk_source_file_id"),
            "similarity": float(getattr(chunk, "similarity", 0.0) or 0.0),
            "weighted_score": None,
            "filter_reason": reason,
        }
        if include_content:
            content = getattr(chunk, "content", None) or ""
            entry["content"] = content[:_CONTENT_PREVIEW_CHARS]
        traces.append(entry)
    return traces


# @lat: [[knowledge#Retrieval Playground And Trace]]
async def persist_trace(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    query_hash: str,
    knowledge_set_id: str,
    profile_id: str | None,
    profile_version: int | None,
    slice_results: list[dict[str, Any]] | None,
    timing: dict[str, Any] | None,
    filter_summary: dict[str, Any] | None,
    chunk_traces: list[dict[str, Any]] | None,
    latency_ms: int,
) -> RetrievalTrace:
    row = RetrievalTrace(
        query_hash=query_hash,
        knowledge_set_id=knowledge_set_id,
        profile_id=profile_id,
        profile_version=profile_version,
        member_id=member.member_id,
        org_id=member.org_id,
        slice_results=slice_results,
        timing=timing,
        filter_summary=filter_summary,
        chunk_traces=chunk_traces,
        latency_ms=latency_ms,
    )
    db.add(row)
    await db.flush()
    return row

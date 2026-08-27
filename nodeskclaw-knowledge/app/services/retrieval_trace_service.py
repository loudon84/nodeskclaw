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


def build_execution_slices(slice_results: list[Any]) -> list[dict[str, Any]]:
    slices: list[dict[str, Any]] = []
    for item in slice_results:
        params_safe_view = {
            "dataset_id": getattr(item, "dataset_id", None),
            "runtime_mode": getattr(item, "runtime_mode", None),
            "access_scope": getattr(item, "access_scope", None),
            "aggregate_security_fallback": getattr(item, "aggregate_security_fallback", False),
        }
        slices.append(
            {
                "knowledge_base_id": getattr(item, "knowledge_base_id", None),
                "access_scope": getattr(item, "access_scope", None),
                "runtime_mode": getattr(item, "runtime_mode", None),
                "params_safe_view": params_safe_view,
                "candidate_count": getattr(item, "candidate_count", 0),
                "safe_count": getattr(item, "safe_count", 0),
                "fallback": getattr(item, "fallback_used", False),
                "fallback_reason": getattr(item, "fallback_reason", None),
                "latency_ms": getattr(item, "latency_ms", 0),
                "status": getattr(item, "status", None),
                "error_code": getattr(item, "error_code", None),
            }
        )
    return slices


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
            "index_type": getattr(item, "index_type", "chunk"),
            "runtime_mode": getattr(item, "runtime_mode", None),
            "access_scope": getattr(item, "access_scope", None),
            "fallback_used": getattr(item, "fallback_used", False),
            "fallback_reason": getattr(item, "fallback_reason", None),
        }
        for item in slice_results
    ]


def build_trace_v2_summary(
    *,
    query_type: str | None,
    requested_indexes: list[str] | None,
    effective_indexes: list[str] | None,
    fallback_used: bool,
    fallback_reason: str | None,
    candidate_count: int,
    security_drop_count: int,
    evidence_count: int,
    timing: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "query_type": query_type,
        "requested_indexes": list(requested_indexes or []),
        "effective_indexes": list(effective_indexes or []),
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "candidate_count": candidate_count,
        "security_drop_count": security_drop_count,
        "evidence_count": evidence_count,
        "timing": timing or {},
    }


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
    query_type: str | None = None,
    requested_indexes: list[str] | None = None,
    effective_indexes: list[str] | None = None,
    fallback_used: bool | None = None,
    fallback_reason: str | None = None,
    execution_slices: list[dict[str, Any]] | None = None,
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
        query_type=query_type,
        requested_indexes=list(requested_indexes) if requested_indexes is not None else None,
        effective_indexes=list(effective_indexes) if effective_indexes is not None else None,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        execution_slices=execution_slices,
    )
    db.add(row)
    await db.flush()
    return row

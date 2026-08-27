"""Runtime response to Evidence type classification."""

# @lat: [[knowledge-objects#Knowledge Evidence]]
from __future__ import annotations

from app.integrations.ragflow.models import RagflowChunk
from app.models.enums import RuntimeRetrievalMode

_SUMMARY_MARKERS = frozenset({"raptor", "summary", "hierarchical_summary", "compiled"})
_GRAPH_MARKERS = frozenset({"graph", "kg", "entity", "relation", "graph_path"})


def _marker_hit(meta: dict, markers: frozenset[str]) -> bool:
    for key, value in meta.items():
        if str(key).startswith("nk_"):
            continue
        key_lower = str(key).lower()
        if key_lower in markers:
            return True
        if isinstance(value, str) and value.lower() in markers:
            return True
        if isinstance(value, bool) and value and key_lower in markers:
            return True
    chunk_type = str(meta.get("type") or meta.get("chunk_type") or "").lower()
    if chunk_type and any(m in chunk_type for m in markers):
        return True
    return False


def classify(chunk: RagflowChunk, slice_mode: str) -> str:
    """Classify runtime chunk into evidence_type: chunk | summary | graph_path | graph_hint."""
    meta = dict(chunk.document_metadata or {})
    content = (chunk.content or "").lower()

    if meta.get("questions") or meta.get("question_kwd"):
        return "chunk"

    if meta.get("source_chunk_ids"):
        return "summary"

    if _marker_hit(meta, _SUMMARY_MARKERS) or "raptor" in content[:200]:
        return "summary"

    if _marker_hit(meta, _GRAPH_MARKERS):
        return "graph_path"

    if slice_mode == RuntimeRetrievalMode.graph_assisted.value:
        return "graph_hint"

    return "chunk"

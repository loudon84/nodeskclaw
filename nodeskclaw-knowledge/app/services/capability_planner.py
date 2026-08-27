"""Capability Planner — effective capability plan from query + runtime + index state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.enums import IndexRetrievalStatus, IndexStateStatus, IndexType

_RULES: list[dict[str, Any]] = [
    {
        "query_type": "graph",
        "match": ["关系", "图谱", "关联", "related", "graph", "entity"],
        "requested": [IndexType.graph.value, IndexType.chunk.value],
        "fallback": [IndexType.chunk.value],
        "reason_codes": ["rule_graph_keywords"],
    },
    {
        "query_type": "outline",
        "match": ["目录", "大纲", "outline", "toc", "章节"],
        "requested": [IndexType.outline.value, IndexType.chunk.value],
        "fallback": [IndexType.chunk.value],
        "reason_codes": ["rule_outline_keywords"],
    },
    {
        "query_type": "table",
        "match": ["表格", "table", "统计"],
        "requested": [IndexType.table.value, IndexType.chunk.value],
        "fallback": [IndexType.chunk.value],
        "reason_codes": ["rule_table_keywords"],
    },
    {
        "query_type": "summary",
        "match": ["总结", "摘要", "summary", "概述"],
        "requested": [IndexType.hierarchical_summary.value, IndexType.chunk.value],
        "fallback": [IndexType.chunk.value],
        "reason_codes": ["rule_summary_keywords"],
    },
    {
        "query_type": "question",
        "match": ["如何", "怎么", "什么", "why", "how", "what", "faq"],
        "requested": [IndexType.question.value, IndexType.chunk.value],
        "fallback": [IndexType.chunk.value],
        "reason_codes": ["rule_question_keywords"],
    },
]


@dataclass
class CapabilityPlan:
    query_type: str = "general"
    requested_indexes: list[str] = field(default_factory=lambda: [IndexType.chunk.value])
    effective_indexes: list[str] = field(default_factory=lambda: [IndexType.chunk.value])
    selected_indexes: list[str] = field(default_factory=lambda: [IndexType.chunk.value])
    fallback_indexes: list[str] = field(default_factory=lambda: [IndexType.chunk.value])
    reason_codes: list[str] = field(default_factory=lambda: ["rule_default_chunk"])
    degraded: list[str] = field(default_factory=list)
    fallback_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_type": self.query_type,
            "requested_indexes": list(self.requested_indexes),
            "effective_indexes": list(self.effective_indexes),
            "selected_indexes": list(self.selected_indexes),
            "fallback_indexes": list(self.fallback_indexes),
            "reason_codes": list(self.reason_codes),
            "degraded": list(self.degraded),
            "fallback_used": self.fallback_used,
        }


def _index_usable(
    index_type: str,
    *,
    available_indexes: set[str],
    build_states: dict[str, str],
    retrieval_states: dict[str, str],
    capabilities: dict[str, Any] | None,
) -> tuple[bool, str | None]:
    from app.services.index_registry import is_index_retrieval_ready, is_runtime_supported

    if index_type not in available_indexes:
        return False, "unavailable"
    build_status = build_states.get(index_type)
    if build_status in {
        IndexStateStatus.unsupported.value,
        IndexStateStatus.not_built.value,
        IndexStateStatus.failed.value,
        IndexStateStatus.building.value,
        IndexStateStatus.stale.value,
    }:
        return False, build_status or "not_built"
    retrieval_status = retrieval_states.get(index_type, IndexRetrievalStatus.unavailable.value)
    if retrieval_status in {
        IndexRetrievalStatus.unsupported.value,
        IndexRetrievalStatus.unavailable.value,
        IndexRetrievalStatus.degraded.value,
    }:
        return False, retrieval_status
    if index_type != IndexType.chunk.value and not is_runtime_supported(index_type, capabilities):
        return False, "unsupported"
    if index_type != IndexType.chunk.value and not is_index_retrieval_ready(index_type, capabilities):
        return False, "query_unavailable"
    return True, None


def build_capability_plan(
    query: str,
    *,
    available_indexes: list[str] | None = None,
    index_states: dict[str, str] | None = None,
    retrieval_states: dict[str, str] | None = None,
    capabilities: dict[str, Any] | None = None,
    force_chunk_only: bool = False,
) -> CapabilityPlan:
    q = (query or "").lower()
    available = set(available_indexes or [IndexType.chunk.value])
    build_states = index_states or {}
    retrieval_map = retrieval_states or {}

    matched_rule: dict[str, Any] | None = None
    for rule in _RULES:
        if any(token.lower() in q for token in rule["match"]):
            matched_rule = rule
            break

    if force_chunk_only:
        return CapabilityPlan(
            query_type="general",
            requested_indexes=[IndexType.chunk.value],
            effective_indexes=[IndexType.chunk.value],
            selected_indexes=[IndexType.chunk.value],
            fallback_indexes=[IndexType.chunk.value],
            reason_codes=["flag_force_chunk_only"],
        )

    query_type = matched_rule["query_type"] if matched_rule else "general"
    requested = list(matched_rule["requested"]) if matched_rule else [IndexType.chunk.value]
    fallback = list(matched_rule["fallback"]) if matched_rule else [IndexType.chunk.value]
    reason_codes = list(matched_rule["reason_codes"]) if matched_rule else ["rule_default_chunk"]

    effective: list[str] = []
    degraded: list[str] = []
    for index_type in requested:
        ok, reason = _index_usable(
            index_type,
            available_indexes=available,
            build_states=build_states,
            retrieval_states=retrieval_map,
            capabilities=capabilities,
        )
        if ok:
            effective.append(index_type)
        elif reason:
            degraded.append(f"{index_type}:{reason}")

    if not effective:
        if IndexType.chunk.value in available:
            effective = [IndexType.chunk.value]
            reason_codes = list(reason_codes) + ["fallback_chunk_only"]
        fallback_used = True
    else:
        fallback_used = effective == [IndexType.chunk.value] and requested != [IndexType.chunk.value]

    fallback_indexes = [i for i in fallback if i in available]
    if IndexType.chunk.value in available and IndexType.chunk.value not in fallback_indexes:
        fallback_indexes.append(IndexType.chunk.value)

    return CapabilityPlan(
        query_type=query_type,
        requested_indexes=requested,
        effective_indexes=effective,
        selected_indexes=effective,
        fallback_indexes=fallback_indexes,
        reason_codes=reason_codes,
        degraded=degraded,
        fallback_used=fallback_used,
    )

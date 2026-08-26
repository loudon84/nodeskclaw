"""Capability Planner — rule-mode selected/fallback indexes (no default LLM)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.enums import IndexType

_RULES: list[dict[str, Any]] = [
    {
        "match": ["关系", "图谱", "关联", "related", "graph", "entity"],
        "selected": [IndexType.graph.value, IndexType.chunk.value],
        "fallback": [IndexType.chunk.value],
        "reason_codes": ["rule_graph_keywords"],
    },
    {
        "match": ["目录", "大纲", "outline", "toc", "章节"],
        "selected": [IndexType.outline.value, IndexType.chunk.value],
        "fallback": [IndexType.chunk.value],
        "reason_codes": ["rule_outline_keywords"],
    },
    {
        "match": ["表格", "table", "统计"],
        "selected": [IndexType.table.value, IndexType.chunk.value],
        "fallback": [IndexType.chunk.value],
        "reason_codes": ["rule_table_keywords"],
    },
    {
        "match": ["总结", "摘要", "summary", "概述"],
        "selected": [IndexType.hierarchical_summary.value, IndexType.chunk.value],
        "fallback": [IndexType.chunk.value],
        "reason_codes": ["rule_summary_keywords"],
    },
]


@dataclass
class CapabilityPlan:
    selected_indexes: list[str] = field(default_factory=lambda: [IndexType.chunk.value])
    fallback_indexes: list[str] = field(default_factory=lambda: [IndexType.chunk.value])
    reason_codes: list[str] = field(default_factory=lambda: ["rule_default_chunk"])
    degraded: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_indexes": list(self.selected_indexes),
            "fallback_indexes": list(self.fallback_indexes),
            "reason_codes": list(self.reason_codes),
            "degraded": list(self.degraded),
        }


def build_capability_plan(
    query: str,
    *,
    available_indexes: list[str] | None = None,
    index_states: dict[str, str] | None = None,
) -> CapabilityPlan:
    """Rule-mode planner. Missing Graph/index is degraded, never ACL failure."""
    q = (query or "").lower()
    available = set(available_indexes or [IndexType.chunk.value])
    states = index_states or {}

    matched: CapabilityPlan | None = None
    for rule in _RULES:
        if any(token.lower() in q for token in rule["match"]):
            matched = CapabilityPlan(
                selected_indexes=list(rule["selected"]),
                fallback_indexes=list(rule["fallback"]),
                reason_codes=list(rule["reason_codes"]),
            )
            break
    if matched is None:
        matched = CapabilityPlan()

    selected: list[str] = []
    degraded: list[str] = []
    for index_type in matched.selected_indexes:
        status = states.get(index_type)
        if index_type not in available or status in {"unsupported", "not_built", "failed"}:
            degraded.append(f"{index_type}:unavailable")
            continue
        if status == "stale":
            degraded.append(f"{index_type}:stale")
        selected.append(index_type)

    if not selected:
        selected = [IndexType.chunk.value] if IndexType.chunk.value in available else []
        if IndexType.chunk.value not in matched.reason_codes:
            matched.reason_codes = list(matched.reason_codes) + ["fallback_chunk_only"]

    fallback = [i for i in matched.fallback_indexes if i in available]
    if IndexType.chunk.value in available and IndexType.chunk.value not in fallback:
        fallback.append(IndexType.chunk.value)

    return CapabilityPlan(
        selected_indexes=selected,
        fallback_indexes=fallback,
        reason_codes=list(matched.reason_codes),
        degraded=degraded,
    )

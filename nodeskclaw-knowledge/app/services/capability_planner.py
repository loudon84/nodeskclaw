"""Capability Planner — per-KB mode/policy from query + runtime + index state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.models.enums import IndexRetrievalStatus, IndexStateStatus, IndexType, RuntimeRetrievalMode

_RULES: list[dict[str, Any]] = [
    {
        "query_type": "graph",
        "match": ["关系", "图谱", "关联", "related", "graph", "entity"],
        "preferred_mode": RuntimeRetrievalMode.graph_assisted.value,
        "reason_codes": ["rule_graph_keywords"],
    },
    {
        "query_type": "outline",
        "match": ["目录", "大纲", "outline", "toc", "章节"],
        "preferred_mode": RuntimeRetrievalMode.toc_enhanced.value,
        "reason_codes": ["rule_outline_keywords"],
    },
    {
        "query_type": "summary",
        "match": ["总结", "摘要", "summary", "概述"],
        "preferred_mode": RuntimeRetrievalMode.compiled_assisted.value,
        "reason_codes": ["rule_summary_keywords"],
    },
    {
        "query_type": "question",
        "match": ["如何", "怎么", "什么", "why", "how", "what", "faq"],
        "preferred_mode": RuntimeRetrievalMode.semantic.value,
        "retrieval_features": ["auto_questions"],
        "reason_codes": ["rule_question_keywords"],
    },
]

_FILTERED_DENIED_MODES = {
    RuntimeRetrievalMode.graph_assisted.value,
    RuntimeRetrievalMode.compiled_assisted.value,
}


@dataclass
class KnowledgeBaseExecutionCapability:
    knowledge_base_id: str
    access_scope: str
    runtime_binding_status: str | None = None
    runtime_capabilities: dict[str, Any] = field(default_factory=dict)
    index_states: dict[str, str] = field(default_factory=dict)
    retrieval_states: dict[str, str] = field(default_factory=dict)
    allowed_modes: list[str] = field(default_factory=lambda: [RuntimeRetrievalMode.semantic.value])
    denied_modes: list[str] = field(default_factory=list)
    selected_mode: str = RuntimeRetrievalMode.semantic.value
    retrieval_features: list[str] = field(default_factory=list)
    query_type: str = "general"
    reason_codes: list[str] = field(default_factory=lambda: ["rule_default_chunk"])
    degraded: list[str] = field(default_factory=list)
    fallback_mode: str = RuntimeRetrievalMode.semantic.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_base_id": self.knowledge_base_id,
            "access_scope": self.access_scope,
            "runtime_binding_status": self.runtime_binding_status,
            "allowed_modes": list(self.allowed_modes),
            "denied_modes": list(self.denied_modes),
            "selected_mode": self.selected_mode,
            "retrieval_features": list(self.retrieval_features),
            "query_type": self.query_type,
            "reason_codes": list(self.reason_codes),
            "degraded": list(self.degraded),
            "fallback_mode": self.fallback_mode,
        }


@dataclass
class CapabilityPlan:
    query_type: str = "general"
    kb_capabilities: dict[str, KnowledgeBaseExecutionCapability] = field(default_factory=dict)
    reason_codes: list[str] = field(default_factory=lambda: ["rule_default_chunk"])
    degraded: list[str] = field(default_factory=list)
    fallback_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_type": self.query_type,
            "kb_capabilities": {kb_id: cap.to_dict() for kb_id, cap in self.kb_capabilities.items()},
            "reason_codes": list(self.reason_codes),
            "degraded": list(self.degraded),
            "fallback_used": self.fallback_used,
        }


def _index_usable(
    index_type: str,
    *,
    build_states: dict[str, str],
    retrieval_states: dict[str, str],
    capabilities: dict[str, Any] | None,
) -> tuple[bool, str | None]:
    from app.services.index_registry import is_index_retrieval_ready, is_runtime_supported

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


def _mode_index_requirement(mode: str) -> str | None:
    mapping = {
        RuntimeRetrievalMode.graph_assisted.value: IndexType.graph.value,
        RuntimeRetrievalMode.compiled_assisted.value: IndexType.hierarchical_summary.value,
    }
    return mapping.get(mode)


def _runtime_toc_available(capabilities: dict[str, Any] | None) -> bool:
    caps = capabilities or {}
    return bool(caps.get("supports_toc_enhance"))


def _profile_allows_mode(mode: str, profile_policy: dict[str, Any]) -> bool:
    if mode == RuntimeRetrievalMode.compiled_assisted.value:
        return bool(profile_policy.get("allow_summary", True))
    if mode == RuntimeRetrievalMode.graph_assisted.value:
        return bool(profile_policy.get("allow_graph", True))
    if mode == RuntimeRetrievalMode.toc_enhanced.value:
        return bool(profile_policy.get("allow_toc_enhance", True))
    return True


def _flag_allows_mode(mode: str) -> bool:
    if mode == RuntimeRetrievalMode.graph_assisted.value:
        return settings.KNOWLEDGE_V2_GRAPH_RUNTIME_ENABLED
    if mode == RuntimeRetrievalMode.compiled_assisted.value:
        return settings.KNOWLEDGE_V2_SUMMARY_RUNTIME_ENABLED
    if mode == RuntimeRetrievalMode.toc_enhanced.value:
        return settings.KNOWLEDGE_V2_TOC_ENHANCE_ENABLED
    return True


def build_kb_execution_capability(
    query: str,
    *,
    knowledge_base_id: str,
    access_scope: str,
    capabilities: dict[str, Any] | None = None,
    index_states: dict[str, str] | None = None,
    retrieval_states: dict[str, str] | None = None,
    runtime_binding_status: str | None = None,
    profile_policy: dict[str, Any] | None = None,
    force_semantic_only: bool = False,
) -> KnowledgeBaseExecutionCapability:
    q = (query or "").lower()
    build_states = index_states or {}
    retrieval_map = retrieval_states or {}
    policy = profile_policy or {}

    matched_rule: dict[str, Any] | None = None
    for rule in _RULES:
        if any(token.lower() in q for token in rule["match"]):
            matched_rule = rule
            break

    query_type = matched_rule["query_type"] if matched_rule else "general"
    preferred_mode = (
        RuntimeRetrievalMode.semantic.value
        if force_semantic_only
        else (matched_rule.get("preferred_mode", RuntimeRetrievalMode.semantic.value) if matched_rule else RuntimeRetrievalMode.semantic.value)
    )
    reason_codes = list(matched_rule["reason_codes"]) if matched_rule else ["rule_default_chunk"]
    retrieval_features: list[str] = []
    if not force_semantic_only and matched_rule and matched_rule.get("retrieval_features"):
        if policy.get("allow_question_enrichment", True) and settings.KNOWLEDGE_V2_QUESTION_INDEX_ENABLED:
            idx_ok, _ = _index_usable(
                IndexType.question.value,
                build_states=build_states,
                retrieval_states=retrieval_map,
                capabilities=capabilities,
            )
            if idx_ok:
                retrieval_features = list(matched_rule["retrieval_features"])

    allowed_modes = [RuntimeRetrievalMode.semantic.value]
    denied_modes: list[str] = []
    degraded: list[str] = []

    candidate_modes = [
        RuntimeRetrievalMode.semantic.value,
        RuntimeRetrievalMode.compiled_assisted.value,
        RuntimeRetrievalMode.graph_assisted.value,
        RuntimeRetrievalMode.toc_enhanced.value,
    ]
    for mode in candidate_modes:
        if mode == RuntimeRetrievalMode.semantic.value:
            continue
        if access_scope == "filtered" and mode in _FILTERED_DENIED_MODES:
            denied_modes.append(mode)
            continue
        if not _profile_allows_mode(mode, policy):
            denied_modes.append(mode)
            continue
        if not _flag_allows_mode(mode):
            denied_modes.append(mode)
            continue
        if mode == RuntimeRetrievalMode.toc_enhanced.value:
            if _runtime_toc_available(capabilities):
                allowed_modes.append(mode)
            else:
                degraded.append(f"{mode}:toc_unavailable")
                denied_modes.append(mode)
            continue
        req_index = _mode_index_requirement(mode)
        if req_index:
            ok, reason = _index_usable(
                req_index,
                build_states=build_states,
                retrieval_states=retrieval_map,
                capabilities=capabilities,
            )
            if ok:
                allowed_modes.append(mode)
            elif reason:
                degraded.append(f"{mode}:{reason}")
                denied_modes.append(mode)
        else:
            allowed_modes.append(mode)

    if preferred_mode not in allowed_modes and preferred_mode != RuntimeRetrievalMode.semantic.value:
        req_index = _mode_index_requirement(preferred_mode)
        reason = "unsupported"
        if preferred_mode == RuntimeRetrievalMode.toc_enhanced.value:
            reason = "toc_unavailable" if not _runtime_toc_available(capabilities) else "unsupported"
        elif req_index:
            _, idx_reason = _index_usable(
                req_index,
                build_states=build_states,
                retrieval_states=retrieval_map,
                capabilities=capabilities,
            )
            if idx_reason:
                reason = idx_reason
        degraded.append(f"{preferred_mode}:{reason}")

    selected_mode = preferred_mode
    fallback_used = False
    if selected_mode not in allowed_modes:
        if preferred_mode != RuntimeRetrievalMode.semantic.value:
            fallback_used = True
            reason_codes = list(reason_codes) + ["fallback_semantic"]
        selected_mode = RuntimeRetrievalMode.semantic.value

    fallback_mode = str(policy.get("fallback_policy") or RuntimeRetrievalMode.semantic.value)
    if fallback_mode not in {m.value for m in RuntimeRetrievalMode}:
        fallback_mode = RuntimeRetrievalMode.semantic.value

    return KnowledgeBaseExecutionCapability(
        knowledge_base_id=knowledge_base_id,
        access_scope=access_scope,
        runtime_binding_status=runtime_binding_status,
        runtime_capabilities=dict(capabilities or {}),
        index_states=dict(build_states),
        retrieval_states=dict(retrieval_map),
        allowed_modes=allowed_modes,
        denied_modes=denied_modes,
        selected_mode=selected_mode,
        retrieval_features=retrieval_features,
        query_type=query_type,
        reason_codes=reason_codes,
        degraded=degraded,
        fallback_mode=fallback_mode,
    )


def build_capability_plan(
    query: str,
    *,
    kb_access_scopes: dict[str, str],
    kb_capabilities_input: dict[str, dict[str, Any]] | None = None,
    kb_index_states: dict[str, dict[str, str]] | None = None,
    kb_retrieval_states: dict[str, dict[str, str]] | None = None,
    kb_binding_status: dict[str, str] | None = None,
    profile_policy: dict[str, Any] | None = None,
    force_semantic_only: bool = False,
) -> CapabilityPlan:
    kb_caps: dict[str, KnowledgeBaseExecutionCapability] = {}
    all_reason_codes: list[str] = []
    all_degraded: list[str] = []
    any_fallback = False

    caps_input = kb_capabilities_input or {}
    index_input = kb_index_states or {}
    retrieval_input = kb_retrieval_states or {}
    binding_input = kb_binding_status or {}

    for kb_id, access_scope in kb_access_scopes.items():
        cap = build_kb_execution_capability(
            query,
            knowledge_base_id=kb_id,
            access_scope=access_scope,
            capabilities=caps_input.get(kb_id),
            index_states=index_input.get(kb_id),
            retrieval_states=retrieval_input.get(kb_id),
            runtime_binding_status=binding_input.get(kb_id),
            profile_policy=profile_policy,
            force_semantic_only=force_semantic_only,
        )
        kb_caps[kb_id] = cap
        all_reason_codes.extend(cap.reason_codes)
        all_degraded.extend(cap.degraded)
        if cap.selected_mode == RuntimeRetrievalMode.semantic.value and cap.query_type != "general":
            any_fallback = True

    query_type = "general"
    if kb_caps:
        query_type = next(iter(kb_caps.values())).query_type

    deduped_reasons = list(dict.fromkeys(all_reason_codes))
    return CapabilityPlan(
        query_type=query_type,
        kb_capabilities=kb_caps,
        reason_codes=deduped_reasons or ["rule_default_chunk"],
        degraded=all_degraded,
        fallback_used=any_fallback,
    )

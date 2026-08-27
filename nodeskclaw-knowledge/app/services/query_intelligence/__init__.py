"""Query intelligence package — intent, terminology, policy gate, optional LLM planner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings


@dataclass
class QueryAnalysis:
    intent: str = "general"
    expanded_terms: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    planner_proposal: dict[str, Any] | None = None
    gate_decisions: list[str] = field(default_factory=list)
    fallback_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "expanded_terms": list(self.expanded_terms),
            "reason_codes": list(self.reason_codes),
            "planner_proposal": self.planner_proposal,
            "gate_decisions": list(self.gate_decisions),
            "fallback_used": self.fallback_used,
        }


_INTENT_KEYWORDS: dict[str, list[str]] = {
    "graph": ["关系", "图谱", "关联", "related", "graph", "entity"],
    "outline": ["目录", "大纲", "outline", "toc", "章节"],
    "summary": ["总结", "摘要", "summary", "概述"],
    "question": ["如何", "怎么", "什么", "why", "how", "what", "faq"],
    "table": ["表格", "table", "列", "row", "字段"],
}


def analyze_intent(query: str) -> tuple[str, list[str]]:
    lowered = query.lower()
    for intent, keywords in _INTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in lowered:
                return intent, [f"intent_keyword:{keyword}"]
    return "general", ["intent_default"]


def expand_terminology(query: str, terms: list | None) -> tuple[list[str], list[str]]:
    if not settings.KNOWLEDGE_V23_TERM_EXPANSION_ENABLED or not terms:
        return [], ["term_expansion_disabled"]
    expanded: list[str] = []
    reasons: list[str] = []
    lowered = query.lower()
    for item in terms:
        if not isinstance(item, dict):
            continue
        canonical = str(item.get("canonical") or item.get("term") or "")
        aliases = item.get("aliases") or []
        if not canonical:
            continue
        if canonical.lower() in lowered:
            expanded.append(canonical)
            reasons.append("term_expansion_canonical_hit")
        for alias in aliases:
            alias_text = str(alias)
            if alias_text.lower() in lowered and canonical not in expanded:
                expanded.append(canonical)
                reasons.append("term_expansion_alias_hit")
                break
    return expanded, reasons or ["term_expansion_no_hit"]


def apply_policy_gate(
    *,
    intent: str,
    access_scope: str,
    profile_policy: dict[str, Any] | None = None,
    planner_proposal: dict[str, Any] | None = None,
) -> tuple[bool, list[str]]:
    decisions: list[str] = []
    denied_modes = {"graph_assisted", "compiled_assisted"}
    if access_scope == "filtered" and intent in {"graph", "summary"}:
        decisions.append("gate_denied_filtered_aggregate")
        return False, decisions
    if planner_proposal:
        proposed_mode = planner_proposal.get("preferred_mode")
        if access_scope == "filtered" and proposed_mode in denied_modes:
            decisions.append("gate_denied_llm_proposal")
            return False, decisions
        decisions.append("gate_llm_proposal_reviewed")
    policy = profile_policy or {}
    if intent == "outline" and policy.get("allow_outline_artifact") is False:
        decisions.append("gate_outline_disabled_by_profile")
        return False, decisions
    if intent == "table" and policy.get("allow_table_artifact") is False:
        decisions.append("gate_table_disabled_by_profile")
        return False, decisions
    decisions.append("gate_allowed")
    return True, decisions


async def propose_with_llm(
    query: str,
    *,
    timeout_seconds: float = 2.0,
) -> tuple[dict[str, Any] | None, bool]:
    if not settings.KNOWLEDGE_V23_LLM_PLANNER_ENABLED:
        return None, False
    try:
        from app.services.query_intelligence.llm_planner import propose_plan

        return await propose_plan(query, timeout_seconds=timeout_seconds)
    except Exception:
        return None, True


async def analyze_query(
    query: str,
    *,
    terms: list | None = None,
    access_scope: str = "full",
    profile_policy: dict[str, Any] | None = None,
) -> QueryAnalysis:
    intent, intent_reasons = analyze_intent(query)
    expanded, term_reasons = expand_terminology(query, terms)
    proposal, fallback_used = await propose_with_llm(query)
    allowed, gate_decisions = apply_policy_gate(
        intent=intent,
        access_scope=access_scope,
        profile_policy=profile_policy,
        planner_proposal=proposal,
    )
    if not allowed and proposal:
        proposal = None
        fallback_used = True
        gate_decisions.append("planner_proposal_rejected")
    return QueryAnalysis(
        intent=intent,
        expanded_terms=expanded,
        reason_codes=intent_reasons + term_reasons,
        planner_proposal=proposal,
        gate_decisions=gate_decisions,
        fallback_used=fallback_used,
    )

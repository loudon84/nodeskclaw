"""FederatedRetrievalPlanner — sole production Provider Selection owner."""

# @lat: [[knowledge#Product Delivery V24]]
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.models.enums import RuntimeRetrievalMode
from app.services.capability_planner import (
    CapabilityPlan,
    KnowledgeBaseExecutionCapability,
    build_capability_plan,
)
from app.services.permission_service import AccessPlan
from app.services.query_intelligence import QueryAnalysis

MODE_TO_PROVIDER: dict[str, str] = {
    RuntimeRetrievalMode.semantic.value: "semantic",
    RuntimeRetrievalMode.graph_assisted.value: "ragflow_graph",
    RuntimeRetrievalMode.compiled_assisted.value: "ragflow_compilation",
    RuntimeRetrievalMode.toc_enhanced.value: "ragflow_toc",
}

INTENT_ARTIFACT_PROVIDER: dict[str, str] = {
    "outline": "artifact_outline",
    "table": "artifact_table",
}


@dataclass
class FederationProviderPlan:
    knowledge_base_id: str
    provider: str
    access_scope: str
    budget: int = 1024
    selected_mode: str = RuntimeRetrievalMode.semantic.value
    retrieval_features: list[str] = field(default_factory=list)
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_base_id": self.knowledge_base_id,
            "provider": self.provider,
            "access_scope": self.access_scope,
            "budget": self.budget,
            "selected_mode": self.selected_mode,
            "retrieval_features": list(self.retrieval_features),
            "weight": self.weight,
        }


@dataclass
class FederationExecutionPlan:
    query_intent: str
    providers: list[FederationProviderPlan]
    kb_capabilities: dict[str, KnowledgeBaseExecutionCapability]
    fusion: str = "weighted_rrf"
    reason_codes: list[str] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    fallback_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_intent": self.query_intent,
            "providers": [item.to_dict() for item in self.providers],
            "fusion": self.fusion,
            "reason_codes": list(self.reason_codes),
            "diagnostics": list(self.diagnostics),
            "fallback_used": self.fallback_used,
            "kb_capabilities": {
                kb_id: cap.to_dict() for kb_id, cap in self.kb_capabilities.items()
            },
        }


def _artifact_provider_allowed(intent: str, profile_policy: dict[str, Any] | None) -> bool:
    policy = profile_policy or {}
    if intent == "outline":
        return bool(policy.get("allow_outline_artifact", True)) and settings.KNOWLEDGE_V23_OUTLINE_ENABLED
    if intent == "table":
        return bool(policy.get("allow_table_artifact", True)) and settings.KNOWLEDGE_V23_TABLE_ENABLED
    return False


def _apply_query_analysis_to_capability(
    cap: KnowledgeBaseExecutionCapability,
    query_analysis: QueryAnalysis | None,
) -> KnowledgeBaseExecutionCapability:
    if query_analysis is None or not query_analysis.planner_proposal:
        return cap
    proposed_mode = query_analysis.planner_proposal.get("preferred_mode")
    if not proposed_mode or proposed_mode == cap.selected_mode:
        return cap
    if proposed_mode not in cap.allowed_modes:
        return cap
    if cap.access_scope == "filtered" and proposed_mode in {
        RuntimeRetrievalMode.graph_assisted.value,
        RuntimeRetrievalMode.compiled_assisted.value,
    }:
        return cap
    return KnowledgeBaseExecutionCapability(
        knowledge_base_id=cap.knowledge_base_id,
        access_scope=cap.access_scope,
        runtime_binding_status=cap.runtime_binding_status,
        runtime_capabilities=cap.runtime_capabilities,
        index_states=cap.index_states,
        retrieval_states=cap.retrieval_states,
        allowed_modes=cap.allowed_modes,
        denied_modes=cap.denied_modes,
        selected_mode=str(proposed_mode),
        retrieval_features=list(cap.retrieval_features),
        query_type=cap.query_type,
        reason_codes=list(cap.reason_codes) + ["federation_llm_proposal"],
        degraded=list(cap.degraded),
        fallback_mode=cap.fallback_mode,
        provider=MODE_TO_PROVIDER.get(str(proposed_mode), "semantic"),
    )


def build_federation_plan(
    query: str,
    *,
    manifest: dict[str, Any] | None = None,
    query_analysis: QueryAnalysis | None = None,
    access_plan: AccessPlan | None = None,
    kb_access_scopes: dict[str, str],
    kb_capabilities_input: dict[str, dict[str, Any]] | None = None,
    kb_index_states: dict[str, dict[str, str]] | None = None,
    kb_retrieval_states: dict[str, dict[str, str]] | None = None,
    kb_binding_status: dict[str, str] | None = None,
    profile_policy: dict[str, Any] | None = None,
    force_semantic_only: bool = False,
    weights_by_kb: dict[str, float] | None = None,
) -> FederationExecutionPlan:
    capability_plan: CapabilityPlan = build_capability_plan(
        query,
        kb_access_scopes=kb_access_scopes,
        kb_capabilities_input=kb_capabilities_input,
        kb_index_states=kb_index_states,
        kb_retrieval_states=kb_retrieval_states,
        kb_binding_status=kb_binding_status,
        profile_policy=profile_policy,
        force_semantic_only=force_semantic_only,
    )

    intent = query_analysis.intent if query_analysis else capability_plan.query_type
    diagnostics: list[str] = list(manifest.get("diagnostics") or []) if manifest else []
    reason_codes = list(capability_plan.reason_codes)
    providers: list[FederationProviderPlan] = []
    kb_capabilities: dict[str, KnowledgeBaseExecutionCapability] = {}
    weight_map = weights_by_kb or {}

    for kb_id, cap in capability_plan.kb_capabilities.items():
        adjusted = _apply_query_analysis_to_capability(cap, query_analysis)
        provider = MODE_TO_PROVIDER.get(adjusted.selected_mode, "semantic")
        adjusted = KnowledgeBaseExecutionCapability(
            knowledge_base_id=adjusted.knowledge_base_id,
            access_scope=adjusted.access_scope,
            runtime_binding_status=adjusted.runtime_binding_status,
            runtime_capabilities=adjusted.runtime_capabilities,
            index_states=adjusted.index_states,
            retrieval_states=adjusted.retrieval_states,
            allowed_modes=adjusted.allowed_modes,
            denied_modes=adjusted.denied_modes,
            selected_mode=adjusted.selected_mode,
            retrieval_features=list(adjusted.retrieval_features),
            query_type=adjusted.query_type,
            reason_codes=list(adjusted.reason_codes),
            degraded=list(adjusted.degraded),
            fallback_mode=adjusted.fallback_mode,
            provider=provider,
        )
        kb_capabilities[kb_id] = adjusted
        budget = int((profile_policy or {}).get("candidate_budget") or 1024)
        providers.append(
            FederationProviderPlan(
                knowledge_base_id=kb_id,
                provider=provider,
                access_scope=adjusted.access_scope,
                budget=budget,
                selected_mode=adjusted.selected_mode,
                retrieval_features=list(adjusted.retrieval_features),
                weight=float(weight_map.get(kb_id, 1.0)),
            )
        )

        if query_analysis and _artifact_provider_allowed(query_analysis.intent, profile_policy):
            artifact_provider = INTENT_ARTIFACT_PROVIDER.get(query_analysis.intent)
            if artifact_provider:
                providers.append(
                    FederationProviderPlan(
                        knowledge_base_id=kb_id,
                        provider=artifact_provider,
                        access_scope=adjusted.access_scope,
                        budget=min(64, int((profile_policy or {}).get("artifact_budget") or 64)),
                        selected_mode=adjusted.selected_mode,
                        retrieval_features=[],
                        weight=float(weight_map.get(kb_id, 1.0)),
                    )
                )
                reason_codes.append(f"artifact_provider:{artifact_provider}")

    if access_plan is not None and access_plan.kind.value == "no_access":
        diagnostics.append("federation_no_access")

    return FederationExecutionPlan(
        query_intent=intent,
        providers=providers,
        kb_capabilities=kb_capabilities,
        fusion="weighted_rrf" if settings.KNOWLEDGE_V23_RRF_FUSION_ENABLED else "weighted_similarity",
        reason_codes=list(dict.fromkeys(reason_codes)),
        diagnostics=diagnostics,
        fallback_used=capability_plan.fallback_used or bool(query_analysis and query_analysis.fallback_used),
    )

"""Query intelligence and RRF fusion tests."""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.integrations.ragflow.models import RagflowChunk
from app.services.query_intelligence import analyze_query, apply_policy_gate
from app.services.retrieval_merge_service import _rank_by_rrf, _rank_by_weighted_similarity


@pytest.mark.asyncio
async def test_analyze_query_graph_intent():
    result = await analyze_query("请展示实体关系图谱")
    assert result.intent == "graph"
    assert result.reason_codes[0].startswith("intent_keyword")


def test_policy_gate_denies_graph_for_filtered_access():
    allowed, decisions = apply_policy_gate(intent="graph", access_scope="filtered")
    assert allowed is False
    assert "gate_denied_filtered_aggregate" in decisions


@pytest.mark.asyncio
async def test_llm_planner_filtered_access_rejects_graph_proposal(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V23_LLM_PLANNER_ENABLED", True)
    result = await analyze_query(
        "graph overview",
        access_scope="filtered",
        profile_policy={},
    )
    assert result.fallback_used or any("gate_denied" in item for item in result.gate_decisions)


def test_rrf_fusion_produces_ranked_candidates():
    chunk_a = RagflowChunk(id="c1", content="a", similarity=0.9, dataset_id="ds1")
    chunk_b = RagflowChunk(id="c2", content="b", similarity=0.8, dataset_id="ds1")
    chunk_c = RagflowChunk(id="c3", content="c", similarity=0.7, dataset_id="ds1")
    modes = [
        (chunk_a, "semantic"),
        (chunk_b, "graph_assisted"),
        (chunk_c, "semantic"),
    ]
    weights = {"ds1": 1.0}
    weighted = _rank_by_weighted_similarity(modes, weights)
    rrf, fusion = _rank_by_rrf(modes, weights)
    assert fusion["strategy"] == "weighted_rrf"
    assert len(rrf) == len(weighted)

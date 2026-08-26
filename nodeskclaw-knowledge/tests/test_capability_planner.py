"""Capability planner and evidence cleaner tests."""

from app.integrations.ragflow.models import RagflowChunk
from app.services import capability_planner
from app.services.chunk_security_service import EvidenceItem, evidence_from_chunk


def test_capability_plan_default_chunk():
    plan = capability_planner.build_capability_plan("hello world")
    assert "chunk" in plan.selected_indexes
    assert "rule_default_chunk" in plan.reason_codes


def test_capability_plan_graph_keywords_degrade_when_unsupported():
    plan = capability_planner.build_capability_plan(
        "查找实体关系图谱",
        available_indexes=["chunk", "graph"],
        index_states={"graph": "unsupported", "chunk": "ready"},
    )
    assert "chunk" in plan.selected_indexes
    assert any(d.startswith("graph:") for d in plan.degraded)
    assert "graph" not in plan.selected_indexes


def test_evidence_from_chunk():
    chunk = RagflowChunk(
        id="c1",
        content="x",
        document_id="d1",
        document_metadata={"nk_source_file_id": "sf1", "nk_file_version_id": "v1"},
    )
    item = evidence_from_chunk(chunk)
    assert item.evidence_type == "chunk"
    assert item.source_refs[0]["source_file_id"] == "sf1"


def test_graph_without_refs_is_evidence_item():
    item = EvidenceItem(evidence_id="g1", evidence_type="graph_path", content="path")
    assert item.source_refs == []

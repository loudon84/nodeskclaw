"""Capability planner and evidence cleaner tests."""

from app.integrations.ragflow.models import RagflowChunk
from app.models.enums import RuntimeRetrievalMode
from app.services import capability_planner
from app.services.chunk_security_service import EvidenceItem, evidence_from_chunk


def test_capability_plan_default_semantic():
    plan = capability_planner.build_capability_plan(
        "hello world",
        kb_access_scopes={"kb1": "full"},
    )
    assert "kb1" in plan.kb_capabilities
    assert plan.kb_capabilities["kb1"].selected_mode == RuntimeRetrievalMode.semantic.value
    assert "rule_default_chunk" in plan.reason_codes


def test_capability_plan_graph_keywords_degrade_when_unsupported():
    plan = capability_planner.build_capability_plan(
        "查找实体关系图谱",
        kb_access_scopes={"kb1": "full"},
        kb_index_states={"kb1": {"graph": "unsupported", "chunk": "ready"}},
        kb_retrieval_states={"kb1": {"graph": "unsupported", "chunk": "ready"}},
    )
    cap = plan.kb_capabilities["kb1"]
    assert cap.selected_mode == RuntimeRetrievalMode.semantic.value
    assert any(d.startswith("graph_assisted:") for d in cap.degraded)
    assert RuntimeRetrievalMode.graph_assisted.value in cap.denied_modes


def test_capability_plan_force_semantic_only():
    plan = capability_planner.build_capability_plan(
        "查找实体关系图谱",
        kb_access_scopes={"kb1": "full"},
        kb_index_states={"kb1": {"graph": "ready", "chunk": "ready"}},
        kb_retrieval_states={"kb1": {"graph": "ready", "chunk": "ready"}},
        force_semantic_only=True,
    )
    assert plan.kb_capabilities["kb1"].selected_mode == RuntimeRetrievalMode.semantic.value


def test_filtered_access_denies_aggregate_modes():
    plan = capability_planner.build_capability_plan(
        "查找实体关系图谱",
        kb_access_scopes={"kb1": "filtered"},
        kb_index_states={"kb1": {"graph": "ready", "chunk": "ready"}},
        kb_retrieval_states={"kb1": {"graph": "ready", "chunk": "ready"}},
        profile_policy={"allow_graph": True, "allow_summary": True},
    )
    cap = plan.kb_capabilities["kb1"]
    assert RuntimeRetrievalMode.graph_assisted.value in cap.denied_modes
    assert RuntimeRetrievalMode.compiled_assisted.value in cap.denied_modes
    assert cap.selected_mode == RuntimeRetrievalMode.semantic.value


def test_toc_enhanced_without_outline_index_when_runtime_supports(monkeypatch):
    monkeypatch.setattr(capability_planner.settings, "KNOWLEDGE_V2_TOC_ENHANCE_ENABLED", True)
    plan = capability_planner.build_capability_plan(
        "文档目录大纲章节",
        kb_access_scopes={"kb1": "full"},
        kb_capabilities_input={"kb1": {"supports_toc_enhance": True}},
        kb_index_states={"kb1": {"chunk": "ready"}},
        kb_retrieval_states={"kb1": {"chunk": "ready"}},
        profile_policy={"allow_toc_enhance": True},
    )
    cap = plan.kb_capabilities["kb1"]
    assert RuntimeRetrievalMode.toc_enhanced.value in cap.allowed_modes


def test_evidence_from_chunk_uses_normalizer():
    chunk = RagflowChunk(
        id="c1",
        content="x",
        document_id="d1",
        document_metadata={"nk_source_file_id": "sf1", "nk_file_version_id": "v1"},
    )
    item = evidence_from_chunk(chunk)
    assert item.evidence_type == "chunk"
    assert item.source_refs[0]["source_file_id"] == "sf1"


def test_evidence_from_chunk_summary_marker():
    chunk = RagflowChunk(
        id="c2",
        content="summary text",
        document_id="d2",
        document_metadata={"raptor": True, "nk_source_file_id": "sf1"},
    )
    item = evidence_from_chunk(chunk, slice_mode="compiled_assisted")
    assert item.evidence_type == "summary"


def test_graph_without_refs_is_evidence_item():
    item = EvidenceItem(evidence_id="g1", evidence_type="graph_path", content="path")
    assert item.source_refs == []

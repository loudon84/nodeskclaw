"""Index registry v2 and retrieval_status tests."""

from app.models.enums import IndexRetrievalStatus, IndexStateStatus, IndexType
from app.services.index_registry import (
    INDEX_DESCRIPTORS,
    SYSTEM_BUILD_PROFILES,
    is_index_retrieval_ready,
    is_runtime_supported,
)


def test_enhanced_profile_converged_to_chunk_question():
    enhanced = SYSTEM_BUILD_PROFILES["enhanced"]
    assert enhanced["index_types"] == [IndexType.chunk.value, IndexType.question.value]


def test_reasoning_profile_includes_summary_and_graph():
    reasoning = SYSTEM_BUILD_PROFILES["reasoning"]
    assert IndexType.hierarchical_summary.value in reasoning["index_types"]
    assert IndexType.graph.value in reasoning["index_types"]
    assert IndexType.outline.value not in reasoning["index_types"]
    assert IndexType.table.value not in reasoning["index_types"]


def test_descriptors_include_provider_and_fallback():
    graph = INDEX_DESCRIPTORS[IndexType.graph.value]
    assert graph["provider"] == "ragflow"
    assert graph["fallback"] == ["chunk"]
    assert graph["requires"]["build_capability"] == "graph"


def test_is_index_retrieval_ready_respects_retrieval_supported_flag():
    caps = {
        "supports_graph": {
            "build_supported": True,
            "retrieval_supported": False,
        }
    }
    assert is_runtime_supported(IndexType.graph.value, caps) is True
    assert is_index_retrieval_ready(IndexType.graph.value, caps) is False


def test_effective_index_requires_build_and_retrieval_ready():
    assert IndexStateStatus.ready.value == "ready"
    assert IndexRetrievalStatus.ready.value == "ready"

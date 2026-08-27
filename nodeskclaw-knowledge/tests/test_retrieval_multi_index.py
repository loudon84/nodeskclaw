"""Multi-index retrieval merge, fallback and evidence dedup."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.integrations.ragflow.models import RagflowChunk
from app.models.enums import RuntimeRetrievalMode
from app.services.chunk_security_service import evidence_from_chunk
from app.services.retrieval_merge_service import (
    MergeExecutionResult,
    _apply_aggregate_gate,
    _dedup_key,
    _normalize_content,
    execute_and_merge,
)
from app.services.retrieval_planner import RetrievalPlan, RuntimeExecutionSlice


def test_evidence_from_chunk_uses_normalizer_not_nk_tags():
    chunk = RagflowChunk(
        id="c1",
        content="hello",
        document_id="d1",
        document_metadata={
            "nk_source_file_id": "sf1",
            "nk_file_version_id": "fv1",
            "nk_knowledge_base_id": "kb1",
            "nk_index_type": "graph",
            "nk_evidence_type": "graph_path",
        },
    )
    item = evidence_from_chunk(chunk, slice_mode="semantic")
    assert item.evidence_type == "chunk"
    assert item.index_type == "semantic"
    assert item.lineage_status == "active"
    assert item.source_refs[0]["knowledge_base_id"] == "kb1"


def test_dedup_key_same_content():
    meta = {"nk_source_file_id": "sf1", "nk_file_version_id": "fv1"}
    a = RagflowChunk(id="a", content="Hello  world", document_id="d1", document_metadata=meta, positions=[[1]])
    b = RagflowChunk(id="b", content="hello world", document_id="d2", document_metadata=meta, positions=[[1]])
    assert _dedup_key(a) == _dedup_key(b)
    assert _normalize_content("  A  B ") == "a b"


def test_aggregate_gate_filtered_denies_graph():
    slice_ = RuntimeExecutionSlice(
        knowledge_base_id="kb1",
        dataset_id="ds1",
        access_scope="filtered",
        mode=RuntimeRetrievalMode.graph_assisted,
        document_ids=["d1"],
        use_kg=True,
    )
    gated, fallback = _apply_aggregate_gate(slice_)
    assert fallback is True
    assert gated.mode == RuntimeRetrievalMode.semantic
    assert gated.use_kg is False
    assert gated.include_knowledge_compilation is False


def test_aggregate_gate_full_allows_graph():
    slice_ = RuntimeExecutionSlice(
        knowledge_base_id="kb1",
        dataset_id="ds1",
        access_scope="full",
        mode=RuntimeRetrievalMode.graph_assisted,
        use_kg=True,
    )
    gated, fallback = _apply_aggregate_gate(slice_)
    assert fallback is False
    assert gated.use_kg is True


@pytest.mark.asyncio
async def test_non_semantic_slice_fallback_to_semantic_on_failure():
    db = MagicMock()
    ragflow = AsyncMock()
    calls: list[dict] = []

    async def _retrieve(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise RuntimeError("graph unavailable")
        return SimpleNamespace(chunks=[RagflowChunk(id="c1", content="ok", document_id="d1", similarity=0.9)])

    ragflow.retrieve = _retrieve
    plan = RetrievalPlan(
        slices=[
            RuntimeExecutionSlice(
                knowledge_base_id="kb1",
                dataset_id="ds1",
                access_scope="full",
                mode=RuntimeRetrievalMode.graph_assisted,
                use_kg=True,
            )
        ]
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.services.retrieval_merge_service.chunk_security_service.clean_chunks_with_modes",
            AsyncMock(
                return_value=SimpleNamespace(
                    safe_chunks=[RagflowChunk(id="c1", content="ok", document_id="d1", similarity=0.9)],
                    filtered_count=0,
                    filter_counts=lambda: {},
                    dropped=[],
                    chunk_modes=[(RagflowChunk(id="c1", content="ok", document_id="d1", similarity=0.9), "semantic")],
                )
            ),
        )
        result = await execute_and_merge(
            db,
            ragflow,
            plan,
            allowed_source_file_ids=set(),
            query="q",
            top_k=8,
            top_n=8,
            similarity_threshold=0.2,
            vector_similarity_weight=0.7,
            keyword=False,
            highlight=False,
            rerank_id=None,
            cross_languages=[],
        )

    assert isinstance(result, MergeExecutionResult)
    assert result.slice_results[0].fallback_used is True
    assert result.fallback_used is True
    assert len(calls) == 2
    assert calls[0].get("use_kg") is True
    assert calls[1].get("use_kg") in {None, False}

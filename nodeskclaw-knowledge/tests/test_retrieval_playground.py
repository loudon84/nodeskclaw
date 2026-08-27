"""Retrieval Playground + Trace unit tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError, ForbiddenError
from app.models.enums import AccessPlanKind, ProfileStatus, RuntimeRetrievalMode
from app.schemas.principal import KnowledgePrincipal
from app.services.permission_service import AccessPlan
from app.services.retrieval_merge_service import MergeExecutionResult, MergeTiming, MergedChunk
from app.services.retrieval_planner import RetrievalPlan, RuntimeExecutionSlice
from app.services.retrieval_service import playground_retrieve
from app.services.retrieval_trace_service import build_chunk_traces, build_filter_summary


def _member(**kwargs) -> KnowledgePrincipal:
    base = dict(
        user_id="u1",
        member_id="m1",
        org_id="o1",
        name="Zhang",
        department="sales",
        member_role="member",
        is_active=True,
        is_super_admin=False,
    )
    base.update(kwargs)
    return KnowledgePrincipal(**base)


def test_build_filter_summary_shape():
    summary = build_filter_summary(
        candidates=42,
        filter_counts={"unauthorized": 3, "superseded": 1, "metadata_mismatch": 0, "unknown": 2},
        returned=8,
    )
    assert summary == {
        "candidates": 42,
        "unauthorized": 3,
        "superseded": 1,
        "metadata_mismatch": 0,
        "returned": 8,
    }


def test_build_chunk_traces_omits_content_by_default(monkeypatch):
    monkeypatch.setattr("app.services.retrieval_trace_service.settings.DEBUG_CONTENT_LOGGING", False)
    chunk = SimpleNamespace(
        id="c1",
        document_id="d1",
        content="secret full text",
        similarity=0.9,
        document_metadata={"nk_source_file_id": "sf1"},
    )
    traces = build_chunk_traces(merged=[MergedChunk(chunk=chunk, weighted_score=0.9, weight=1.0)])
    assert traces[0]["chunk_id"] == "c1"
    assert "content" not in traces[0]


@pytest.mark.asyncio
async def test_playground_requires_manage():
    db = MagicMock()
    db.commit = AsyncMock()
    ragflow = AsyncMock()
    member = _member()
    ks = SimpleNamespace(id="set1", org_id="o1", status="active")

    with (
        patch(
            "app.services.retrieval_service.knowledge_set_service.get_knowledge_set",
            new=AsyncMock(return_value=ks),
        ),
        patch("app.services.retrieval_service.has_set_permission", new=AsyncMock(return_value=False)),
    ):
        with pytest.raises(ForbiddenError):
            await playground_retrieve(db, member, ragflow, knowledge_set_id="set1", query="hello")


@pytest.mark.asyncio
async def test_playground_allows_draft_profile_and_returns_timing():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.get = AsyncMock(
        return_value=SimpleNamespace(
            id="p-draft",
            knowledge_set_id="set1",
            version=2,
            config={"top_n": 3, "top_k": 10, "similarity_threshold": 0.2},
            status=ProfileStatus.draft.value,
            deleted_at=None,
        )
    )
    ragflow = AsyncMock()
    member = _member()
    ks = SimpleNamespace(id="set1", org_id="o1", status="active")
    kbs = [SimpleNamespace(id="kb1", ragflow_dataset_id="ds1", metadata_schema=None)]
    plan_access = AccessPlan(
        kind=AccessPlanKind.full_access,
        dataset_ids=["ds1"],
        full_dataset_ids=["ds1"],
        partial_slices=[],
        source_file_ids=["sf1"],
        knowledge_base_ids=["kb1"],
    )
    plan = RetrievalPlan(
        plan_kind=AccessPlanKind.full_access,
        allowed_source_file_ids=["sf1"],
        slices=[
            RuntimeExecutionSlice(
                knowledge_base_id="kb1",
                dataset_id="ds1",
                access_scope="full",
                mode=RuntimeRetrievalMode.semantic,
                document_ids=None,
                weight=1.0,
            )
        ],
    )
    chunk = SimpleNamespace(
        id="c1",
        document_id="d1",
        document_name="a.md",
        document_keyword=None,
        content="hello",
        similarity=0.8,
        positions=None,
        term_similarity=None,
        vector_similarity=None,
        highlight=None,
        document_metadata={"nk_source_file_id": "sf1", "nk_knowledge_base_id": "kb1"},
    )
    merge_result = MergeExecutionResult(
        merged=[MergedChunk(chunk=chunk, weighted_score=0.8, weight=1.0)],
        candidate_count=5,
        filtered_count=2,
        ragflow_call_count=1,
        slice_results=[],
        timing=MergeTiming(ragflow_ms=12, security_ms=3, merge_ms=1),
        filter_counts={"unauthorized": 1, "superseded": 1, "metadata_mismatch": 0, "unknown": 0},
        dropped_chunks=[],
    )

    with (
        patch(
            "app.services.retrieval_service.knowledge_set_service.get_knowledge_set",
            new=AsyncMock(return_value=ks),
        ),
        patch("app.services.retrieval_service.has_set_permission", new=AsyncMock(return_value=True)),
        patch(
            "app.services.retrieval_service.knowledge_set_service.list_bound_knowledge_bases",
            new=AsyncMock(return_value=kbs),
        ),
        patch("app.services.retrieval_service.build_access_plan", new=AsyncMock(return_value=plan_access)),
        patch(
            "app.services.retrieval_service.knowledge_set_service.list_set_items",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.retrieval_service.runtime_binding_service.get_dataset_id",
            new=AsyncMock(return_value="ds1"),
        ),
        patch("app.services.retrieval_service.retrieval_planner.build_retrieval_plan", return_value=plan),
        patch(
            "app.services.retrieval_service.retrieval_merge_service.execute_and_merge",
            new=AsyncMock(return_value=merge_result),
        ),
        patch(
            "app.services.retrieval_service.retrieval_trace_service.persist_trace",
            new=AsyncMock(return_value=SimpleNamespace(id="t1")),
        ) as persist,
    ):
        result = await playground_retrieve(
            db,
            member,
            ragflow,
            knowledge_set_id="set1",
            query="hello",
            profile_id="p-draft",
            include_trace=True,
        )

    assert result["query"] == "hello"
    assert result["plan"] == {"knowledge_bases": 1, "slices": 1}
    assert result["timing"]["ragflow_ms"] == 12
    assert result["timing"]["security_ms"] == 3
    assert result["timing"]["merge_ms"] == 1
    assert "acl_ms" in result["timing"]
    assert "total_ms" in result["timing"]
    assert result["filter_summary"]["candidates"] == 5
    assert result["filter_summary"]["unauthorized"] == 1
    assert result["filter_summary"]["superseded"] == 1
    assert result["filter_summary"]["returned"] == 1
    assert len(result["results"]) == 1
    persist.assert_awaited()
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_playground_rejects_archived_profile():
    db = MagicMock()
    db.get = AsyncMock(
        return_value=SimpleNamespace(
            id="p-arch",
            knowledge_set_id="set1",
            version=1,
            config={},
            status=ProfileStatus.archived.value,
            deleted_at=None,
        )
    )
    ragflow = AsyncMock()
    member = _member()
    ks = SimpleNamespace(id="set1", org_id="o1", status="active")
    kbs = [SimpleNamespace(id="kb1", ragflow_dataset_id="ds1", metadata_schema=None)]

    with (
        patch(
            "app.services.retrieval_service.knowledge_set_service.get_knowledge_set",
            new=AsyncMock(return_value=ks),
        ),
        patch("app.services.retrieval_service.has_set_permission", new=AsyncMock(return_value=True)),
        patch(
            "app.services.retrieval_service.knowledge_set_service.list_bound_knowledge_bases",
            new=AsyncMock(return_value=kbs),
        ),
    ):
        with pytest.raises(BadRequestError) as exc:
            await playground_retrieve(
                db,
                member,
                ragflow,
                knowledge_set_id="set1",
                query="hello",
                profile_id="p-arch",
            )

    assert exc.value.message_key == "errors.knowledge.profile_not_active"

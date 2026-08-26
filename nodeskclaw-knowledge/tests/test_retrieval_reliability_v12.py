"""Retrieval fail_closed / degraded and usage_count (PRD §71)."""

from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ServiceUnavailableError
from app.models.enums import AccessPlanKind, RetrievalOrigin, RetrievalSliceKind
from app.services.permission_service import AccessPlan
from app.services.retrieval_merge_service import MergeExecutionResult, RetrievalSliceResult
from app.services.retrieval_planner import RetrievalPlan, RetrievalSlice
from app.services.retrieval_service import retrieve


def _member():
    return SimpleNamespace(member_id="m1", org_id="o1")


def _ks():
    return SimpleNamespace(
        id="set1",
        org_id="o1",
        status="active",
        usage_count=0,
        last_used_at=None,
    )


def _failed_merge():
    return MergeExecutionResult(
        merged=[],
        candidate_count=2,
        filtered_count=0,
        ragflow_call_count=2,
        slice_results=[
            RetrievalSliceResult(
                knowledge_base_id="kb1",
                dataset_id="ds1",
                status="success",
                latency_ms=10,
                candidate_count=2,
                safe_count=2,
            ),
            RetrievalSliceResult(
                knowledge_base_id="kb2",
                dataset_id="ds2",
                status="failed",
                latency_ms=5000,
                candidate_count=0,
                safe_count=0,
                error_code="errors.knowledge.ragflow_unavailable",
            ),
        ],
    )


def _plan_with_slices():
    return RetrievalPlan(
        plan_kind=AccessPlanKind.filtered_access,
        allowed_source_file_ids=["sf1"],
        slices=[
            RetrievalSlice(
                kind=RetrievalSliceKind.full_dataset,
                dataset_id="ds1",
                knowledge_base_id="kb1",
            ),
            RetrievalSlice(
                kind=RetrievalSliceKind.full_dataset,
                dataset_id="ds2",
                knowledge_base_id="kb2",
            ),
        ],
    )


def _enter_retrieve_patches(stack: ExitStack, *, ks, profile, plan, merge_result):
    plan_access = AccessPlan(
        kind=AccessPlanKind.filtered_access,
        dataset_ids=["ds1", "ds2"],
        full_dataset_ids=["ds1", "ds2"],
        partial_slices=[],
        source_file_ids=["sf1"],
        knowledge_base_ids=["kb1", "kb2"],
    )
    kbs = [
        SimpleNamespace(id="kb1", ragflow_dataset_id="ds1", metadata_schema=None),
        SimpleNamespace(id="kb2", ragflow_dataset_id="ds2", metadata_schema=None),
    ]
    stack.enter_context(
        patch(
            "app.services.retrieval_service.knowledge_set_service.get_knowledge_set",
            new=AsyncMock(return_value=ks),
        )
    )
    stack.enter_context(
        patch("app.services.retrieval_service.has_set_permission", new=AsyncMock(return_value=True))
    )
    stack.enter_context(
        patch(
            "app.services.retrieval_service.knowledge_set_service.list_bound_knowledge_bases",
            new=AsyncMock(return_value=kbs),
        )
    )
    stack.enter_context(
        patch(
            "app.services.retrieval_service.retrieval_profile_service.get_active_profile",
            new=AsyncMock(return_value=profile),
        )
    )
    stack.enter_context(
        patch("app.services.retrieval_service.build_access_plan", new=AsyncMock(return_value=plan_access))
    )
    stack.enter_context(
        patch(
            "app.services.retrieval_service.knowledge_set_service.list_set_items",
            new=AsyncMock(return_value=[]),
        )
    )
    stack.enter_context(
        patch(
            "app.services.retrieval_service.runtime_binding_service.get_dataset_id",
            new=AsyncMock(return_value="ds1"),
        )
    )
    stack.enter_context(
        patch("app.services.retrieval_service.retrieval_planner.build_retrieval_plan", return_value=plan)
    )
    stack.enter_context(
        patch(
            "app.services.retrieval_service.retrieval_merge_service.execute_and_merge",
            new=AsyncMock(return_value=merge_result),
        )
    )


@pytest.mark.asyncio
async def test_slice_timeout_fail_closed_raises_503():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    ks = _ks()
    profile = SimpleNamespace(
        id="p1",
        knowledge_set_id="set1",
        config={"failure_policy": "fail_closed", "top_n": 8},
        status="active",
    )
    with ExitStack() as stack:
        _enter_retrieve_patches(
            stack, ks=ks, profile=profile, plan=_plan_with_slices(), merge_result=_failed_merge()
        )
        with pytest.raises(ServiceUnavailableError) as exc:
            await retrieve(db, _member(), AsyncMock(), knowledge_set_id="set1", query="q")

    assert exc.value.status_code == 503
    assert exc.value.message_key == "errors.knowledge.retrieval_unavailable"
    assert ks.usage_count == 0


@pytest.mark.asyncio
async def test_slice_timeout_degraded_returns_status():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    ks = _ks()
    profile = SimpleNamespace(
        id="p1",
        knowledge_set_id="set1",
        config={"failure_policy": "degraded", "top_n": 8},
        status="active",
    )
    with ExitStack() as stack:
        _enter_retrieve_patches(
            stack, ks=ks, profile=profile, plan=_plan_with_slices(), merge_result=_failed_merge()
        )
        result = await retrieve(db, _member(), AsyncMock(), knowledge_set_id="set1", query="q")

    assert result["status"] == "degraded"
    assert result["diagnostics"]["failed_slice_count"] == 1
    assert ks.usage_count == 1


@pytest.mark.asyncio
async def test_usage_count_increments_for_chat_origin_once():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    ks = _ks()
    profile = SimpleNamespace(
        id="p1",
        knowledge_set_id="set1",
        config={"failure_policy": "degraded", "top_n": 8},
        status="active",
    )
    with ExitStack() as stack:
        _enter_retrieve_patches(
            stack, ks=ks, profile=profile, plan=_plan_with_slices(), merge_result=_failed_merge()
        )
        await retrieve(
            db,
            _member(),
            AsyncMock(),
            knowledge_set_id="set1",
            query="q",
            origin=RetrievalOrigin.chat.value,
        )

    assert ks.usage_count == 1


@pytest.mark.asyncio
async def test_usage_count_skips_evaluation_origin():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    ks = _ks()
    profile = SimpleNamespace(
        id="p1",
        knowledge_set_id="set1",
        config={"failure_policy": "degraded", "top_n": 8},
        status="active",
    )
    with ExitStack() as stack:
        _enter_retrieve_patches(
            stack, ks=ks, profile=profile, plan=_plan_with_slices(), merge_result=_failed_merge()
        )
        await retrieve(
            db,
            _member(),
            AsyncMock(),
            knowledge_set_id="set1",
            query="q",
            origin=RetrievalOrigin.evaluation.value,
        )

    assert ks.usage_count == 0

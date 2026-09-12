from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ServiceUnavailableError
from app.models.enums import AccessPlanKind, IndexRetrievalStatus, IndexType, RuntimeRetrievalMode
from app.models.index_state import IndexState
from app.services import index_state_service
from app.services.permission_service import AccessPlan
from app.services.retrieval_merge_service import MergeExecutionResult, RetrievalSliceResult
from app.services.retrieval_planner import RetrievalPlan, RuntimeExecutionSlice
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
        deleted_at=None,
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
                status="failed",
                latency_ms=10,
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
            RuntimeExecutionSlice(
                knowledge_base_id="kb1",
                dataset_id="ds1",
                access_scope="full",
                mode=RuntimeRetrievalMode.semantic,
            ),
        ],
    )


@pytest.mark.asyncio
async def test_mark_chunk_retrieval_unavailable_sets_owner_status():
    state = IndexState(
        org_id="o1",
        knowledge_base_id="kb1",
        index_type=IndexType.chunk.value,
        retrieval_status=IndexRetrievalStatus.ready.value,
    )
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=state)
    updated = await index_state_service.mark_chunk_retrieval_unavailable(db, knowledge_base_ids=["kb1"])
    assert updated == [state]
    assert state.retrieval_status == IndexRetrievalStatus.unavailable.value
    assert state.validation_payload["runtime_operation"] == "fail_closed_writeback"


@pytest.mark.asyncio
async def test_fail_closed_retrieve_triggers_indexstate_writeback():
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
    writeback = AsyncMock(return_value=[])
    plan_access = AccessPlan(
        kind=AccessPlanKind.filtered_access,
        dataset_ids=["ds1"],
        full_dataset_ids=["ds1"],
        partial_slices=[],
        source_file_ids=["sf1"],
        knowledge_base_ids=["kb1"],
    )
    kbs = [SimpleNamespace(id="kb1", ragflow_dataset_id="ds1", metadata_schema=None)]
    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "app.services.retrieval_service.knowledge_set_service.get_knowledge_set",
                new=AsyncMock(return_value=ks),
            )
        )
        stack.enter_context(patch("app.services.retrieval_service.has_set_permission", new=AsyncMock(return_value=True)))
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
        stack.enter_context(patch("app.services.retrieval_service.build_access_plan", new=AsyncMock(return_value=plan_access)))
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
            patch(
                "app.services.retrieval_service.runtime_binding_service.get_binding",
                new=AsyncMock(return_value=None),
            )
        )
        stack.enter_context(patch("app.services.index_state_service.list_states_for_kb", new=AsyncMock(return_value=[])))
        stack.enter_context(patch("app.services.index_state_service.mark_chunk_retrieval_unavailable", new=writeback))
        stack.enter_context(
            patch("app.services.retrieval_service.retrieval_planner.build_retrieval_plan", return_value=_plan_with_slices())
        )
        stack.enter_context(
            patch(
                "app.services.retrieval_service.retrieval_merge_service.execute_and_merge",
                new=AsyncMock(return_value=_failed_merge()),
            )
        )
        with pytest.raises(ServiceUnavailableError) as exc:
            await retrieve(db, _member(), AsyncMock(), knowledge_set_id="set1", query="q")

    assert exc.value.status_code == 503
    assert exc.value.message_key == "errors.knowledge.retrieval_unavailable"
    writeback.assert_awaited()
    kwargs = writeback.await_args.kwargs
    assert kwargs["knowledge_base_ids"] == ["kb1"]

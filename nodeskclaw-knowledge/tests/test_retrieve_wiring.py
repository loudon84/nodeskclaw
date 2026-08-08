"""Retrieve wiring regression: planner receives set_items."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import AccessPlanKind
from app.services.permission_service import AccessPlan
from app.services.retrieval_planner import RetrievalPlan
from app.services.retrieval_service import retrieve


@pytest.mark.asyncio
async def test_retrieve_passes_set_items_to_planner():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    ragflow = AsyncMock()
    member = SimpleNamespace(member_id="m1", org_id="o1")
    ks = SimpleNamespace(
        id="set1",
        org_id="o1",
        status="active",
        usage_count=0,
        last_used_at=None,
    )
    set_items = [SimpleNamespace(knowledge_base_id="kb1", weight=1.5)]
    kbs = [SimpleNamespace(id="kb1", ragflow_dataset_id="ds1")]
    profile = SimpleNamespace(
        id="p1",
        knowledge_set_id="set1",
        config={},
        status="active",
    )
    plan_access = AccessPlan(
        kind=AccessPlanKind.full_access,
        dataset_ids=["ds1"],
        full_dataset_ids=["ds1"],
        partial_slices=[],
        source_file_ids=["sf1"],
        knowledge_base_ids=["kb1"],
    )
    empty_plan = RetrievalPlan(plan_kind=AccessPlanKind.full_access, allowed_source_file_ids=["sf1"])

    with (
        patch("app.services.retrieval_service.knowledge_set_service.get_knowledge_set", new=AsyncMock(return_value=ks)),
        patch("app.services.retrieval_service.has_set_permission", new=AsyncMock(return_value=True)),
        patch(
            "app.services.retrieval_service.knowledge_set_service.list_bound_knowledge_bases",
            new=AsyncMock(return_value=kbs),
        ),
        patch(
            "app.services.retrieval_service.retrieval_profile_service.get_active_profile",
            new=AsyncMock(return_value=profile),
        ),
        patch("app.services.retrieval_service.build_access_plan", new=AsyncMock(return_value=plan_access)),
        patch(
            "app.services.retrieval_service.knowledge_set_service.list_set_items",
            new=AsyncMock(return_value=set_items),
        ),
        patch("app.services.retrieval_service.retrieval_planner.build_retrieval_plan", return_value=empty_plan) as build,
    ):
        result = await retrieve(db, member, ragflow, knowledge_set_id="set1", query="hello")

    build.assert_called_once_with(plan_access, kbs, set_items)
    assert result["chunks"] == []

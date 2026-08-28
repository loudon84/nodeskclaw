"""Retrieve wiring regression: planner receives set_items."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.models.enums import AccessPlanKind, ApplicationStatus, KnowledgeSetStatus
from app.services.permission_service import AccessPlan
from app.services.retrieval_planner import RetrievalPlan
from app.services.retrieval_service import retrieve, retrieve_for_application


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
        patch(
            "app.services.retrieval_service.runtime_binding_service.get_dataset_id",
            new=AsyncMock(return_value="ds1"),
        ),
        patch(
            "app.services.retrieval_service.runtime_binding_service.get_binding",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.index_state_service.list_states_for_kb",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.retrieval_service.retrieval_merge_service.execute_and_merge",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    merged=[],
                    candidate_count=0,
                    filtered_count=0,
                    ragflow_call_count=0,
                    slice_results=[],
                )
            ),
        ),
        patch("app.services.retrieval_service.retrieval_planner.build_retrieval_plan", return_value=empty_plan) as build,
    ):
        result = await retrieve(db, member, ragflow, knowledge_set_id="set1", query="hello")

    build.assert_called_once()
    call_kwargs = build.call_args.kwargs
    assert call_kwargs["metadata_condition"] is None
    assert call_kwargs["dataset_id_by_kb_id"] == {"kb1": "ds1"}
    assert "kb_capabilities" in call_kwargs
    assert call_kwargs["kb_capabilities"]["kb1"].knowledge_base_id == "kb1"
    assert build.call_args.args[0] == plan_access
    assert build.call_args.args[1] == kbs
    assert build.call_args.args[2] == set_items
    assert result["chunks"] == []


def _release_manifest():
    return {
        "schema_version": 1,
        "application_id": "app1",
        "release_version": 1,
        "retrieval_policy_revision_id": "policy-1",
        "answer_model": "release-gpt",
        "knowledge_sets": [
            {
                "knowledge_set_id": "set_ctx",
                "knowledge_bases": [
                    {"knowledge_base_id": "kb_ctx", "weight": 2.0, "knowledge_model_revision_id": "rev-1"},
                ],
            }
        ],
    }


def _release_context():
    manifest = _release_manifest()
    return SimpleNamespace(
        release_id="rel-1",
        channel="stable",
        application_id="app1",
        manifest=manifest,
        manifest_hash="abc123",
        answer_model="release-gpt",
        knowledge_set_ids=["set_ctx"],
        knowledge_bases=[
            {"knowledge_base_id": "kb_ctx", "weight": 2.0, "knowledge_set_id": "set_ctx", "knowledge_model_revision_id": "rev-1"},
        ],
        retrieval_policy_revision_id="policy-1",
        compiled_policy={"candidate_budget": 512, "allow_graph": False},
        integrity_status="healthy",
    )


@pytest.mark.asyncio
async def test_retrieve_for_application_v24_uses_context_not_manifest_set_ids(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V2_APPLICATION_ENABLED", True)
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    db = AsyncMock()
    member = SimpleNamespace(member_id="m1", org_id="o1")
    ragflow = AsyncMock()
    app = SimpleNamespace(
        id="app1",
        org_id="o1",
        status=ApplicationStatus.active.value,
        answer_model="live-gpt",
        active_profile_id="profile-live",
    )
    ctx = _release_context()
    ks = SimpleNamespace(id="set_ctx", status=KnowledgeSetStatus.active.value, org_id="o1", deleted_at=None)
    kb = SimpleNamespace(id="kb_ctx", metadata_schema=None)

    with (
        patch(
            "app.services.knowledge_application_service.get_application",
            new=AsyncMock(return_value=app),
        ),
        patch(
            "app.services.retrieval_service.has_application_permission",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "app.services.release_runtime_service.resolve_application_release",
            new=AsyncMock(return_value=ctx),
        ),
        patch(
            "app.services.knowledge_base_service.get_knowledge_base",
            new=AsyncMock(return_value=kb),
        ),
        patch(
            "app.services.retrieval_service.knowledge_set_service.get_knowledge_set",
            new=AsyncMock(return_value=ks),
        ),
        patch(
            "app.services.retrieval_service.has_set_permission",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "app.services.retrieval_service._retrieve_for_set",
            new=AsyncMock(return_value={"chunks": [], "status": "empty"}),
        ) as retrieve_set,
        patch(
            "app.services.retrieval_service.knowledge_set_service.list_bound_knowledge_bases",
            new=AsyncMock(),
        ) as list_bound_kbs,
        patch(
            "app.services.retrieval_service.knowledge_set_service.list_set_items",
            new=AsyncMock(),
        ) as list_set_items,
    ):
        result = await retrieve_for_application(
            db, member, ragflow, application_id="app1", query="hello", profile_id="profile-override"
        )

    retrieve_set.assert_awaited_once()
    kwargs = retrieve_set.await_args.kwargs
    assert kwargs["profile_id"] is None
    assert kwargs["compiled_policy"] == ctx.compiled_policy
    assert kwargs["execution_context"] is ctx
    assert kwargs["kbs_override"] == [kb]
    assert kwargs["set_items_override"][0].knowledge_base_id == "kb_ctx"
    assert kwargs["set_items_override"][0].weight == 2.0
    assert kwargs["bump_set_ids"] == ["set_ctx"]
    list_bound_kbs.assert_not_awaited()
    list_set_items.assert_not_awaited()
    assert result["answer_model"] == "release-gpt"
    assert result["knowledge_set_ids"] == ["set_ctx"]
    assert result["manifest_hash"] == "abc123"


@pytest.mark.asyncio
async def test_retrieve_for_set_skips_profile_when_compiled_policy_provided(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V2_MULTI_INDEX_RETRIEVAL_ENABLED", False)
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_FEDERATION_ENABLED", False)
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    ragflow = AsyncMock()
    member = SimpleNamespace(member_id="m1", org_id="o1")
    ks = SimpleNamespace(id="set1", org_id="o1", status="active", usage_count=0, last_used_at=None)
    set_items = [SimpleNamespace(knowledge_base_id="kb1", weight=1.0)]
    kbs = [SimpleNamespace(id="kb1", ragflow_dataset_id="ds1", metadata_schema=None)]
    compiled_policy = {"candidate_budget": 256, "allow_graph": False, "allow_outline_artifact": False}
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
            new=AsyncMock(),
        ) as get_profile,
        patch("app.services.retrieval_service.build_access_plan", new=AsyncMock(return_value=plan_access)),
        patch(
            "app.services.retrieval_service.knowledge_set_service.list_set_items",
            new=AsyncMock(return_value=set_items),
        ),
        patch(
            "app.services.retrieval_service.runtime_binding_service.get_dataset_id",
            new=AsyncMock(return_value="ds1"),
        ),
        patch(
            "app.services.retrieval_service.runtime_binding_service.get_binding",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.index_state_service.list_states_for_kb",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.retrieval_service.retrieval_merge_service.execute_and_merge",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    merged=[],
                    candidate_count=0,
                    filtered_count=0,
                    ragflow_call_count=0,
                    slice_results=[],
                )
            ),
        ),
        patch("app.services.retrieval_service.retrieval_planner.build_retrieval_plan", return_value=empty_plan),
        patch(
            "app.services.query_intelligence.resolve_release_terms",
            new=AsyncMock(return_value=([], ["semantic_model:no_expansion"])),
        ),
        patch(
            "app.services.query_intelligence.analyze_query",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    intent="general",
                    expanded_terms=[],
                    reason_codes=[],
                    planner_proposal=None,
                    gate_decisions=[],
                    fallback_used=False,
                )
            ),
        ),
    ):
        from app.services.retrieval_service import _retrieve_for_set

        await _retrieve_for_set(
            db,
            member,
            ragflow,
            knowledge_set_id="set1",
            query="hello",
            compiled_policy=compiled_policy,
        )

    get_profile.assert_not_awaited()

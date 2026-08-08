"""Retrieval planner slice building."""

from types import SimpleNamespace

from app.models.enums import AccessPlanKind, RetrievalSliceKind
from app.services.permission_service import AccessPlan
from app.services.retrieval_planner import build_retrieval_plan


def _kb(id_: str, dataset_id: str):
    return SimpleNamespace(id=id_, ragflow_dataset_id=dataset_id)


def _item(kb_id: str, weight: float = 1.0):
    return SimpleNamespace(knowledge_base_id=kb_id, weight=weight)


def test_retrieval_planner_full_plus_partial():
    access = AccessPlan(
        kind=AccessPlanKind.filtered_access,
        dataset_ids=["ds_a", "ds_b"],
        full_dataset_ids=["ds_a"],
        partial_slices=[
            {
                "kind": "filtered_documents",
                "dataset_id": "ds_b",
                "knowledge_base_id": "kb_b",
                "document_ids": ["doc_b1", "doc_b2"],
            }
        ],
        source_file_ids=["sf_a1", "sf_b1"],
        knowledge_base_ids=["kb_a", "kb_b"],
    )
    kbs = [_kb("kb_a", "ds_a"), _kb("kb_b", "ds_b")]
    items = [_item("kb_a", 1.0), _item("kb_b", 2.0)]
    plan = build_retrieval_plan(access, kbs, items)

    assert plan.plan_kind == AccessPlanKind.filtered_access
    assert len(plan.slices) == 2
    full_slice = next(s for s in plan.slices if s.kind == RetrievalSliceKind.full_dataset)
    partial_slice = next(s for s in plan.slices if s.kind == RetrievalSliceKind.filtered_documents)
    assert full_slice.dataset_id == "ds_a"
    assert full_slice.knowledge_base_id == "kb_a"
    assert partial_slice.dataset_id == "ds_b"
    assert partial_slice.document_ids == ["doc_b1", "doc_b2"]
    assert partial_slice.weight == 2.0


def test_retrieval_planner_batches_partial_document_ids(monkeypatch):
    monkeypatch.setattr("app.services.retrieval_planner.settings.RETRIEVAL_DOCUMENT_BATCH_SIZE", 2)
    access = AccessPlan(
        kind=AccessPlanKind.filtered_access,
        dataset_ids=["ds_b"],
        full_dataset_ids=[],
        partial_slices=[
            {
                "kind": "filtered_documents",
                "dataset_id": "ds_b",
                "knowledge_base_id": "kb_b",
                "document_ids": ["d1", "d2", "d3", "d4", "d5"],
            }
        ],
        source_file_ids=["sf1"],
        knowledge_base_ids=["kb_b"],
    )
    plan = build_retrieval_plan(access, [_kb("kb_b", "ds_b")], [_item("kb_b", 1.0)])
    assert len(plan.slices) == 3
    assert plan.slices[0].document_ids == ["d1", "d2"]
    assert plan.slices[1].document_ids == ["d3", "d4"]
    assert plan.slices[2].document_ids == ["d5"]

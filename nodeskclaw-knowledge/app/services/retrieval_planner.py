"""Build RetrievalPlan slices from AccessPlan."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import settings
from app.models.enums import AccessPlanKind, RetrievalSliceKind
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_set_item import KnowledgeSetItem
from app.services.permission_service import AccessPlan


@dataclass
class RetrievalSlice:
    kind: RetrievalSliceKind
    dataset_id: str
    knowledge_base_id: str | None = None
    document_ids: list[str] = field(default_factory=list)
    weight: float = 1.0


@dataclass
class RetrievalPlan:
    slices: list[RetrievalSlice] = field(default_factory=list)
    plan_kind: AccessPlanKind = AccessPlanKind.no_access
    allowed_source_file_ids: list[str] = field(default_factory=list)


# @lat: [[knowledge#Retrieval Planner]]
def build_retrieval_plan(
    access_plan: AccessPlan,
    knowledge_bases: list[KnowledgeBase],
    set_items: list[KnowledgeSetItem],
) -> RetrievalPlan:
    if access_plan.kind == AccessPlanKind.no_access:
        return RetrievalPlan(plan_kind=AccessPlanKind.no_access)

    weights = {item.knowledge_base_id: float(item.weight) for item in set_items}
    kb_by_dataset = {kb.ragflow_dataset_id: kb for kb in knowledge_bases if kb.ragflow_dataset_id}
    batch_size = max(1, int(settings.RETRIEVAL_DOCUMENT_BATCH_SIZE))

    slices: list[RetrievalSlice] = []
    for dataset_id in access_plan.full_dataset_ids:
        kb = kb_by_dataset.get(dataset_id)
        kb_id = kb.id if kb else None
        slices.append(
            RetrievalSlice(
                kind=RetrievalSliceKind.full_dataset,
                dataset_id=dataset_id,
                knowledge_base_id=kb_id,
                weight=weights.get(kb_id or "", 1.0),
            )
        )

    for partial in access_plan.partial_slices:
        kb_id = partial.get("knowledge_base_id")
        document_ids = list(partial.get("document_ids") or [])
        weight = weights.get(kb_id or "", 1.0)
        dataset_id = partial["dataset_id"]
        if not document_ids:
            slices.append(
                RetrievalSlice(
                    kind=RetrievalSliceKind.filtered_documents,
                    dataset_id=dataset_id,
                    knowledge_base_id=kb_id,
                    document_ids=[],
                    weight=weight,
                )
            )
            continue
        for start in range(0, len(document_ids), batch_size):
            batch = document_ids[start : start + batch_size]
            slices.append(
                RetrievalSlice(
                    kind=RetrievalSliceKind.filtered_documents,
                    dataset_id=dataset_id,
                    knowledge_base_id=kb_id,
                    document_ids=batch,
                    weight=weight,
                )
            )

    if not slices:
        return RetrievalPlan(
            plan_kind=access_plan.kind,
            allowed_source_file_ids=list(access_plan.source_file_ids),
        )

    return RetrievalPlan(
        slices=slices,
        plan_kind=access_plan.kind,
        allowed_source_file_ids=list(access_plan.source_file_ids),
    )

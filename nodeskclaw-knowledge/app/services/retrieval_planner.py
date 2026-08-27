"""Build RetrievalPlan slices from AccessPlan."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
    metadata_condition: dict[str, Any] | None = None
    index_type: str = "chunk"
    provider: str = "ragflow"
    top_k: int | None = None
    access_scope: str | None = None


@dataclass
class RetrievalPlan:
    slices: list[RetrievalSlice] = field(default_factory=list)
    plan_kind: AccessPlanKind = AccessPlanKind.no_access
    allowed_source_file_ids: list[str] = field(default_factory=list)
    metadata_pushdown: bool = False


def build_metadata_condition(filters: dict[str, list] | None) -> dict[str, Any] | None:
    """Optional RAGFlow metadata_condition; security still relies on local ACL + document_ids."""
    if not filters:
        return None
    conditions: list[dict[str, Any]] = []
    for key, values in filters.items():
        if not values:
            continue
        field_name = key if key.startswith("biz_") or key.startswith("nk_") else f"biz_{key}"
        if len(values) == 1:
            conditions.append({"name": field_name, "comparison_operator": "is", "value": str(values[0])})
        else:
            conditions.append(
                {"name": field_name, "comparison_operator": "in", "value": [str(v) for v in values]}
            )
    if not conditions:
        return None
    return {"logic": "and", "conditions": conditions}


# @lat: [[knowledge#Retrieval Planner]]
def build_retrieval_plan(
    access_plan: AccessPlan,
    knowledge_bases: list[KnowledgeBase],
    set_items: list[KnowledgeSetItem],
    *,
    metadata_condition: dict[str, Any] | None = None,
    pushdown_enabled: bool | None = None,
    dataset_id_by_kb_id: dict[str, str] | None = None,
) -> RetrievalPlan:
    use_pushdown = (
        settings.RAGFLOW_METADATA_PUSHDOWN_ENABLED if pushdown_enabled is None else bool(pushdown_enabled)
    )
    condition = metadata_condition if use_pushdown else None

    if access_plan.kind == AccessPlanKind.no_access:
        return RetrievalPlan(plan_kind=AccessPlanKind.no_access, metadata_pushdown=bool(condition))

    weights = {item.knowledge_base_id: float(item.weight) for item in set_items}
    id_map = dataset_id_by_kb_id or {}
    kb_by_dataset = {
        dataset_id: kb
        for kb in knowledge_bases
        for dataset_id in [id_map.get(kb.id)]
        if dataset_id
    }
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
                metadata_condition=condition,
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
                    metadata_condition=condition,
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
                    metadata_condition=condition,
                )
            )

    if not slices:
        return RetrievalPlan(
            plan_kind=access_plan.kind,
            allowed_source_file_ids=list(access_plan.source_file_ids),
            metadata_pushdown=bool(condition),
        )

    return RetrievalPlan(
        slices=slices,
        plan_kind=access_plan.kind,
        allowed_source_file_ids=list(access_plan.source_file_ids),
        metadata_pushdown=bool(condition),
    )

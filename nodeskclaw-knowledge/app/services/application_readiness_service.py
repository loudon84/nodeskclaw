"""Application readiness checks before publish."""

# @lat: [[knowledge#Application Readiness]]
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import IndexRetrievalStatus, IndexStateStatus, IndexType, KnowledgeSetStatus, RuntimeBindingStatus
from app.models.knowledge_set import KnowledgeSet
from app.schemas.principal import KnowledgePrincipal
from app.services import index_state_service, knowledge_application_service, knowledge_set_service, runtime_binding_service
from app.services.index_registry import is_index_retrieval_ready, is_runtime_supported
from app.services.retrieval_profile_service import get_active_profile, merge_profile_config


@dataclass
class ReadinessIssue:
    code: str
    knowledge_base_id: str | None = None
    knowledge_set_id: str | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code}
        if self.knowledge_base_id is not None:
            payload["knowledge_base_id"] = self.knowledge_base_id
        if self.knowledge_set_id is not None:
            payload["knowledge_set_id"] = self.knowledge_set_id
        if self.message is not None:
            payload["message"] = self.message
        return payload


@dataclass
class ReadinessResult:
    ready: bool
    blocking: list[ReadinessIssue] = field(default_factory=list)
    warnings: list[ReadinessIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "blocking": [item.to_dict() for item in self.blocking],
            "warnings": [item.to_dict() for item in self.warnings],
        }


async def check(
    db: AsyncSession,
    member: KnowledgePrincipal,
    application_id: str,
) -> ReadinessResult:
    await knowledge_application_service.get_application(db, member, application_id)
    set_ids = await knowledge_application_service.list_bound_set_ids(db, application_id)
    blocking: list[ReadinessIssue] = []
    warnings: list[ReadinessIssue] = []
    usable_kb_ids: set[str] = set()

    if not set_ids:
        blocking.append(ReadinessIssue(code="no_knowledge_sets_bound"))
        return ReadinessResult(ready=False, blocking=blocking, warnings=warnings)

    for set_id in set_ids:
        ks = await db.get(KnowledgeSet, set_id)
        if ks is None or ks.deleted_at is not None:
            blocking.append(
                ReadinessIssue(code="knowledge_set_missing", knowledge_set_id=set_id)
            )
            continue
        if ks.status == KnowledgeSetStatus.disabled.value:
            warnings.append(
                ReadinessIssue(
                    code="knowledge_set_disabled",
                    knowledge_set_id=set_id,
                )
            )
            continue

        profile = await get_active_profile(db, set_id)
        if profile is None:
            blocking.append(
                ReadinessIssue(
                    code="retrieval_profile_missing",
                    knowledge_set_id=set_id,
                )
            )

        try:
            kbs = await knowledge_set_service.list_bound_knowledge_bases(db, member, set_id)
        except Exception:
            kbs = []

        if not kbs:
            blocking.append(
                ReadinessIssue(code="knowledge_set_empty", knowledge_set_id=set_id)
            )
            continue

        profile_config = merge_profile_config(profile.config if profile else None)
        for kb in kbs:
            usable_kb_ids.add(kb.id)
            binding = await runtime_binding_service.get_binding(db, kb.id)
            capabilities = (binding.capabilities if binding else None) or {}

            if binding is None or binding.status != RuntimeBindingStatus.ready.value:
                blocking.append(
                    ReadinessIssue(
                        code="runtime_binding_not_ready",
                        knowledge_base_id=kb.id,
                        knowledge_set_id=set_id,
                    )
                )

            chunk_state = await index_state_service.get_or_create_state(
                db,
                org_id=member.org_id,
                knowledge_base_id=kb.id,
                index_type=IndexType.chunk.value,
            )
            if chunk_state.status != IndexStateStatus.ready.value:
                blocking.append(
                    ReadinessIssue(
                        code="runtime_chunk_unavailable",
                        knowledge_base_id=kb.id,
                        knowledge_set_id=set_id,
                    )
                )
            elif chunk_state.retrieval_status != IndexRetrievalStatus.ready.value:
                blocking.append(
                    ReadinessIssue(
                        code="runtime_chunk_retrieval_unavailable",
                        knowledge_base_id=kb.id,
                        knowledge_set_id=set_id,
                    )
                )

            if profile_config.get("allow_graph") and not is_runtime_supported(IndexType.graph.value, capabilities):
                warnings.append(
                    ReadinessIssue(
                        code="graph_mode_incompatible",
                        knowledge_base_id=kb.id,
                        knowledge_set_id=set_id,
                    )
                )
            if profile_config.get("allow_summary") and not is_runtime_supported(
                IndexType.hierarchical_summary.value, capabilities
            ):
                warnings.append(
                    ReadinessIssue(
                        code="summary_mode_incompatible",
                        knowledge_base_id=kb.id,
                        knowledge_set_id=set_id,
                    )
                )
            if profile_config.get("allow_question_enrichment") and not is_index_retrieval_ready(
                IndexType.question.value, capabilities
            ):
                warnings.append(
                    ReadinessIssue(
                        code="question_mode_incompatible",
                        knowledge_base_id=kb.id,
                        knowledge_set_id=set_id,
                    )
                )

    if not usable_kb_ids:
        blocking.append(ReadinessIssue(code="no_usable_knowledge_base"))

    ready = len(blocking) == 0
    if not ready:
        from app.services import metrics_service

        for issue in blocking:
            metrics_service.observe_application_readiness_failure(reason=issue.code)

    return ReadinessResult(ready=ready, blocking=blocking, warnings=warnings)

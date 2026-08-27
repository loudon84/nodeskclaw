"""Runtime Binding service — Dataset identity Authority for KnowledgeBase."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.models.base import not_deleted
from app.models.enums import RuntimeBindingStatus, RuntimeResourceType, RuntimeType
from app.models.knowledge_base import KnowledgeBase
from app.models.runtime_binding import KnowledgeRuntimeBinding

if TYPE_CHECKING:
    from app.runtime.ragflow import RagflowRuntimeAdapter


@dataclass
class ProbePersistResult:
    capabilities: dict[str, Any]
    runtime_version: str | None
    probe_error: str | None = None


async def probe_and_persist_binding_capabilities(
    db: AsyncSession,
    *,
    knowledge_base_id: str,
    adapter: RagflowRuntimeAdapter,
) -> ProbePersistResult:
    from app.runtime import capabilities as runtime_capabilities

    now = datetime.now(UTC)
    probe_error: str | None = None
    capabilities: dict[str, Any]
    runtime_version: str | None
    try:
        reachable, runtime_version, capabilities = await runtime_capabilities.probe_runtime(adapter.client)
        if not reachable:
            probe_error = "ragflow_unreachable"
    except Exception as exc:
        probe_error = str(exc)
        snapshot, version = adapter.get_probe_snapshot()
        if snapshot:
            capabilities = snapshot
            runtime_version = version
        else:
            binding = await get_binding(db, knowledge_base_id)
            capabilities = (binding.capabilities if binding else None) or {}
            runtime_version = binding.runtime_version if binding else None

    binding = await get_binding(db, knowledge_base_id)
    if binding is not None:
        if probe_error is None:
            binding.capabilities = capabilities
            binding.runtime_version = runtime_version
            binding.last_capability_probe_at = now
            binding.last_capability_probe_error = None
        else:
            binding.last_capability_probe_at = now
            binding.last_capability_probe_error = probe_error
        await db.flush()

    return ProbePersistResult(
        capabilities=capabilities,
        runtime_version=runtime_version,
        probe_error=probe_error,
    )


async def probe_all_bindings(db: AsyncSession, adapter: RagflowRuntimeAdapter) -> dict[str, int]:
    result = await db.execute(
        select(KnowledgeRuntimeBinding).where(not_deleted(KnowledgeRuntimeBinding))
    )
    probed = 0
    failed = 0
    for binding in result.scalars().all():
        probe_result = await probe_and_persist_binding_capabilities(
            db,
            knowledge_base_id=binding.knowledge_base_id,
            adapter=adapter,
        )
        if probe_result.probe_error:
            failed += 1
        else:
            probed += 1
    await db.flush()
    return {"probed": probed, "failed": failed}


async def get_binding(
    db: AsyncSession,
    knowledge_base_id: str,
    *,
    runtime_type: str = RuntimeType.ragflow.value,
    resource_type: str = RuntimeResourceType.dataset.value,
) -> KnowledgeRuntimeBinding | None:
    result = await db.execute(
        select(KnowledgeRuntimeBinding).where(
            KnowledgeRuntimeBinding.knowledge_base_id == knowledge_base_id,
            KnowledgeRuntimeBinding.runtime_type == runtime_type,
            KnowledgeRuntimeBinding.resource_type == resource_type,
            not_deleted(KnowledgeRuntimeBinding),
        )
    )
    return result.scalar_one_or_none()


async def get_dataset_id(db: AsyncSession, knowledge_base: KnowledgeBase | str) -> str | None:
    """Resolve RAGFlow dataset id. Binding is Authority when flag enabled; else legacy column."""
    if isinstance(knowledge_base, str):
        kb = await db.get(KnowledgeBase, knowledge_base)
    else:
        kb = knowledge_base
    if kb is None or getattr(kb, "deleted_at", None) is not None:
        return None
    if settings.KNOWLEDGE_V2_RUNTIME_BINDING_ENABLED:
        binding = await get_binding(db, kb.id)
        if binding is not None and binding.status != RuntimeBindingStatus.deleting.value:
            return binding.resource_id
    return kb.ragflow_dataset_id


async def require_dataset_id(db: AsyncSession, knowledge_base: KnowledgeBase | str) -> str:
    """Resolve dataset id or raise kb_not_ready. Prefer over reading kb.ragflow_dataset_id."""
    dataset_id = await get_dataset_id(db, knowledge_base)
    if not dataset_id:
        raise BadRequestError(message="知识库未就绪", message_key="errors.knowledge.kb_not_ready")
    return dataset_id


async def upsert_ragflow_dataset_binding(
    db: AsyncSession,
    *,
    org_id: str,
    knowledge_base_id: str,
    resource_id: str,
    status: str = RuntimeBindingStatus.ready.value,
    runtime_version: str | None = None,
    capabilities: dict | None = None,
    runtime_config: dict | None = None,
    from_probe: bool = False,
) -> KnowledgeRuntimeBinding:
    existing = await get_binding(db, knowledge_base_id)
    now = datetime.now(UTC)
    if existing is not None:
        existing.resource_id = resource_id
        existing.status = status
        existing.runtime_version = runtime_version
        if capabilities is not None and from_probe:
            existing.capabilities = capabilities
            existing.last_capability_probe_at = now
            existing.last_capability_probe_error = None
        elif capabilities is not None and existing.capabilities is None:
            existing.capabilities = capabilities
        if runtime_config is not None:
            existing.runtime_config = runtime_config
        existing.last_synced_at = now
        existing.last_error = None
        await db.flush()
        return existing
    row = KnowledgeRuntimeBinding(
        org_id=org_id,
        knowledge_base_id=knowledge_base_id,
        runtime_type=RuntimeType.ragflow.value,
        resource_type=RuntimeResourceType.dataset.value,
        resource_id=resource_id,
        runtime_version=runtime_version,
        status=status,
        capabilities=capabilities,
        runtime_config=runtime_config,
        last_synced_at=now,
        last_capability_probe_at=now if from_probe and capabilities is not None else None,
    )
    db.add(row)
    await db.flush()
    return row


async def mirror_dataset_id_to_kb(
    db: AsyncSession,
    knowledge_base: KnowledgeBase,
    resource_id: str,
) -> None:
    knowledge_base.ragflow_dataset_id = resource_id


async def backfill_from_knowledge_bases(db: AsyncSession) -> dict[str, int]:
    """Idempotent backfill: each non-null ragflow_dataset_id → one ragflow/dataset Binding."""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.ragflow_dataset_id.is_not(None),
            not_deleted(KnowledgeBase),
        )
    )
    created = 0
    updated = 0
    skipped = 0
    for kb in result.scalars().all():
        if not kb.ragflow_dataset_id:
            skipped += 1
            continue
        existing = await get_binding(db, kb.id)
        if existing is None:
            await upsert_ragflow_dataset_binding(
                db,
                org_id=kb.org_id,
                knowledge_base_id=kb.id,
                resource_id=kb.ragflow_dataset_id,
                status=RuntimeBindingStatus.ready.value,
            )
            created += 1
        elif existing.resource_id != kb.ragflow_dataset_id:
            existing.resource_id = kb.ragflow_dataset_id
            existing.last_synced_at = datetime.now(UTC)
            updated += 1
        else:
            skipped += 1
    await db.flush()
    return {"created": created, "updated": updated, "skipped": skipped}

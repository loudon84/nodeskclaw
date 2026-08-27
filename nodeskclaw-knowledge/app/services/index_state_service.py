"""Index State service — mark STALE / unsupported / ready transitions."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.models.enums import IndexRetrievalStatus, IndexStateStatus, IndexType
from app.models.index_state import IndexState
from app.services import build_profile_service
from app.services.index_registry import is_index_retrieval_ready, is_runtime_supported, list_index_types


async def get_or_create_state(
    db: AsyncSession,
    *,
    org_id: str,
    knowledge_base_id: str,
    index_type: str,
) -> IndexState:
    existing = await db.scalar(
        select(IndexState).where(
            IndexState.knowledge_base_id == knowledge_base_id,
            IndexState.index_type == index_type,
            not_deleted(IndexState),
        )
    )
    if existing is not None:
        return existing
    state = IndexState(
        org_id=org_id,
        knowledge_base_id=knowledge_base_id,
        index_type=index_type,
        status=IndexStateStatus.not_built.value,
    )
    db.add(state)
    await db.flush()
    return state


async def list_states_for_kb(db: AsyncSession, knowledge_base_id: str) -> list[IndexState]:
    rows = await db.scalars(
        select(IndexState).where(
            IndexState.knowledge_base_id == knowledge_base_id,
            not_deleted(IndexState),
        )
    )
    return list(rows.all())


async def ensure_kb_index_states(
    db: AsyncSession,
    *,
    org_id: str,
    kb,
    capabilities: dict | None = None,
) -> list[IndexState]:
    profile = await build_profile_service.resolve_profile_for_kb(db, kb)
    wanted = set(profile.index_types or [])
    wanted.add(IndexType.chunk.value)
    states: list[IndexState] = []
    for index_type in list_index_types():
        if index_type not in wanted and index_type != IndexType.chunk.value:
            continue
        state = await get_or_create_state(
            db,
            org_id=org_id,
            knowledge_base_id=kb.id,
            index_type=index_type,
        )
        if not is_runtime_supported(index_type, capabilities):
            if state.status != IndexStateStatus.unsupported.value:
                state.status = IndexStateStatus.unsupported.value
                state.last_error = "runtime_public_api_unavailable"
            state.retrieval_status = IndexRetrievalStatus.unsupported.value
        elif state.status == IndexStateStatus.unsupported.value:
            state.status = IndexStateStatus.not_built.value
            state.last_error = None
            state.retrieval_status = IndexRetrievalStatus.unavailable.value
        else:
            _sync_retrieval_status(state, index_type, capabilities)
        states.append(state)
    return states


def _sync_retrieval_status(
    state: IndexState,
    index_type: str,
    capabilities: dict | None,
) -> None:
    if state.status != IndexStateStatus.ready.value:
        if state.retrieval_status == IndexRetrievalStatus.ready.value:
            state.retrieval_status = IndexRetrievalStatus.unavailable.value
        return
    if is_index_retrieval_ready(index_type, capabilities):
        state.retrieval_status = IndexRetrievalStatus.ready.value
    else:
        state.retrieval_status = IndexRetrievalStatus.unsupported.value


async def mark_indexes_stale(
    db: AsyncSession,
    *,
    org_id: str,
    kb,
    index_types: list[str] | None = None,
    source_watermark: str | None = None,
    capabilities: dict | None = None,
) -> list[IndexState]:
    profile = await build_profile_service.resolve_profile_for_kb(db, kb)
    targets = index_types or list(profile.index_types or [IndexType.chunk.value])
    updated: list[IndexState] = []
    for index_type in targets:
        if index_type == IndexType.chunk.value:
            continue
        state = await get_or_create_state(
            db,
            org_id=org_id,
            knowledge_base_id=kb.id,
            index_type=index_type,
        )
        if not is_runtime_supported(index_type, capabilities):
            state.status = IndexStateStatus.unsupported.value
            state.last_error = "runtime_public_api_unavailable"
            updated.append(state)
            continue
        if state.status == IndexStateStatus.unsupported.value:
            updated.append(state)
            continue
        state.status = IndexStateStatus.stale.value
        if source_watermark is not None:
            state.source_watermark = source_watermark
        updated.append(state)
    return updated


async def set_state_status(
    db: AsyncSession,
    state: IndexState,
    status: str,
    *,
    build_job_id: str | None = None,
    error: str | None = None,
    capabilities: dict | None = None,
) -> IndexState:
    if status == IndexStateStatus.ready.value and state.status == IndexStateStatus.unsupported.value:
        return state
    state.status = status
    if build_job_id is not None:
        state.last_build_job_id = build_job_id
    if error is not None:
        state.last_error = error
    elif status in {IndexStateStatus.ready.value, IndexStateStatus.building.value}:
        state.last_error = None
    if status == IndexStateStatus.ready.value:
        state.last_built_at = datetime.now(UTC)
        state.build_version = int(state.build_version or 0) + 1
        if capabilities is not None:
            _sync_retrieval_status(state, state.index_type, capabilities)
        else:
            state.retrieval_status = IndexRetrievalStatus.ready.value
    elif status in {IndexStateStatus.failed.value, IndexStateStatus.stale.value}:
        if state.retrieval_status == IndexRetrievalStatus.ready.value:
            state.retrieval_status = IndexRetrievalStatus.degraded.value
    elif status == IndexStateStatus.unsupported.value:
        state.retrieval_status = IndexRetrievalStatus.unsupported.value
    return state

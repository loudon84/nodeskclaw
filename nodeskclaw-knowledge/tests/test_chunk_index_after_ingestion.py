from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import IndexRetrievalStatus, IndexStateStatus, IngestionJobStatus, IndexType
from app.services import build_executors, index_state_service
from app.services.ingestion_service import process_leased_job


def _doc(doc_id: str, *, run: str, chunk_count: int | None):
    return SimpleNamespace(id=doc_id, run=run, chunk_count=chunk_count)


@pytest.mark.asyncio
async def test_inventory_chunk_documents_counts_done_and_pending():
    class Adapter:
        async def list_documents(self, _dataset_id, *, page=1, page_size=50, **kwargs):
            if page == 1:
                return [_doc("d1", run="DONE", chunk_count=3), _doc("d2", run="RUNNING", chunk_count=0)]
            return []

    inventory = await build_executors.inventory_chunk_documents(Adapter(), "ds1")
    assert inventory.documents_total == 2
    assert inventory.documents_ready == 1
    assert inventory.chunks_total == 3
    assert inventory.not_ready_ids == ["d2"]
    assert inventory.build_ready() is False


@pytest.mark.asyncio
async def test_inventory_chunk_documents_ready_when_all_done():
    class Adapter:
        async def list_documents(self, _dataset_id, *, page=1, page_size=50, **kwargs):
            if page == 1:
                return [_doc("d1", run="DONE", chunk_count=2), _doc("d2", run="DONE", chunk_count=4)]
            return []

    inventory = await build_executors.inventory_chunk_documents(Adapter(), "ds1")
    assert inventory.build_ready() is True
    assert inventory.as_output()["runtime_operation"] == "chunk_inventory"


@pytest.mark.asyncio
async def test_apply_chunk_inventory_sets_ready_with_this_dataset_retrieval():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    state = await index_state_service.apply_chunk_inventory(
        db,
        org_id="o1",
        knowledge_base_id="kb1",
        inventory_ready=True,
        retrieval_ready=True,
        summary={"documents_ready": 1},
    )
    assert state.status == IndexStateStatus.ready.value
    assert state.retrieval_status == IndexRetrievalStatus.ready.value
    assert state.index_type == IndexType.chunk.value


@pytest.mark.asyncio
async def test_apply_chunk_inventory_does_not_mark_ready_when_pending():
    existing = SimpleNamespace(
        status=IndexStateStatus.not_built.value,
        retrieval_status=IndexRetrievalStatus.unavailable.value,
        index_type=IndexType.chunk.value,
        last_error=None,
        last_build_job_id=None,
        last_built_at=None,
        build_version=0,
        input_manifest_hash=None,
        input_manifest_summary=None,
    )
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=existing)
    state = await index_state_service.apply_chunk_inventory(
        db,
        org_id="o1",
        knowledge_base_id="kb1",
        inventory_ready=False,
        retrieval_ready=False,
    )
    assert state.status == IndexStateStatus.not_built.value
    assert state.retrieval_status != IndexRetrievalStatus.ready.value


@pytest.mark.asyncio
async def test_sync_chunk_index_after_activation_uses_validate_index_retrieval():
    kb = SimpleNamespace(id="kb1", org_id="o1")
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    adapter = AsyncMock()
    adapter.list_documents = AsyncMock(
        side_effect=lambda *_a, page=1, page_size=50, **_k: (
            [_doc("d1", run="DONE", chunk_count=5)] if page == 1 else []
        )
    )
    adapter.validate_index_retrieval = AsyncMock(return_value=True)

    with patch(
        "app.services.build_executors.runtime_binding_service.require_dataset_id",
        new=AsyncMock(return_value="ds-this"),
    ):
        await build_executors.sync_chunk_index_after_activation(db, kb, adapter)

    adapter.validate_index_retrieval.assert_awaited_once_with(dataset_id="ds-this")


@pytest.mark.asyncio
async def test_process_leased_job_activate_calls_chunk_index_sync():
    job = SimpleNamespace(
        id="job1",
        source_file_id="sf1",
        file_version_id="v1",
        attempt_count=1,
        max_attempts=5,
        status=IngestionJobStatus.parsing.value,
        progress=90,
        next_run_at=None,
        finished_at=None,
        error_code=None,
        error_message=None,
    )
    sf = SimpleNamespace(
        id="sf1",
        org_id="o1",
        knowledge_base_id="kb1",
        active_version_id=None,
        status="updating",
        metadata_=None,
        metadata_revision=1,
    )
    version = SimpleNamespace(
        id="v1",
        ragflow_document_id="doc1",
        parse_status="parsing",
        ragflow_status="RUNNING",
        ragflow_run="RUNNING",
        ragflow_progress=1,
        ragflow_progress_msg=None,
        chunk_count=None,
        token_count=None,
        process_duration=None,
    )
    kb = SimpleNamespace(id="kb1", org_id="o1", ragflow_dataset_id="ds1")
    doc = SimpleNamespace(
        id="doc1",
        run="DONE",
        progress=1,
        progress_msg=None,
        chunk_count=4,
        token_count=10,
        process_duration=1,
        meta_fields={
            "nk_source_file_id": "sf1",
            "nk_file_version_id": "v1",
            "nk_knowledge_base_id": "kb1",
            "nk_org_id": "o1",
            "nk_metadata_revision": "1",
        },
    )

    async def _get(model, oid):
        mapping = {"sf1": sf, "v1": version, "kb1": kb}
        return mapping.get(oid)

    db = MagicMock()
    db.get = AsyncMock(side_effect=_get)
    db.flush = AsyncMock()
    ragflow = AsyncMock()
    ragflow.list_documents = AsyncMock(return_value=[doc])
    sync = AsyncMock()

    with (
        patch(
            "app.services.ingestion_service.runtime_binding_service.get_dataset_id",
            new=AsyncMock(return_value="ds1"),
        ),
        patch(
            "app.services.ingestion_service.build_meta_fields",
            return_value=doc.meta_fields,
        ),
        patch(
            "app.services.ingestion_service.activate_version",
            lambda source, ver, old: setattr(source, "active_version_id", ver.id),
        ),
        patch(
            "app.services.ingestion_service.build_executors.sync_chunk_index_after_activation",
            new=sync,
        ),
    ):
        await process_leased_job(db, ragflow, job)

    assert job.status == IngestionJobStatus.active.value
    sync.assert_awaited_once()


def test_execute_chunk_stage_uses_inventory_chunk_documents_helper():
    import inspect

    source = inspect.getsource(build_executors.execute_chunk_stage)
    assert "inventory_chunk_documents" in source
    assert "documents_total += 1" not in source


def _ready_chunk_state(**overrides):
    state = SimpleNamespace(
        status=IndexStateStatus.ready.value,
        retrieval_status=IndexRetrievalStatus.ready.value,
        index_type=IndexType.chunk.value,
        last_error=None,
        validation_payload=None,
        coverage_payload=None,
        last_validated_at=None,
    )
    for key, value in overrides.items():
        setattr(state, key, value)
    return state


# @lat: [[knowledge-objects#Index State]]
@pytest.mark.asyncio
async def test_ensure_keeps_this_dataset_ready_when_binding_retrieval_unsupported():
    existing = _ready_chunk_state()
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=existing)
    kb = SimpleNamespace(id="kb1", org_id="o1")
    adapter = AsyncMock()
    adapter.validate_index_retrieval = AsyncMock(return_value=True)
    binding_caps = {
        "supports_chunk": {"build_supported": True, "retrieval_supported": False},
    }

    with (
        patch(
            "app.services.index_state_service.build_profile_service.resolve_profile_for_kb",
            new=AsyncMock(return_value=SimpleNamespace(index_types=["chunk"])),
        ),
        patch(
            "app.services.index_state_service.list_index_types",
            return_value=[IndexType.chunk.value],
        ),
        patch(
            "app.services.index_state_service.runtime_binding_service.get_dataset_id",
            new=AsyncMock(return_value="ds-this"),
        ),
    ):
        states = await index_state_service.ensure_kb_index_states(
            db,
            org_id="o1",
            kb=kb,
            capabilities=binding_caps,
            runtime_adapter=adapter,
        )

    assert states[0].retrieval_status == IndexRetrievalStatus.ready.value
    adapter.validate_index_retrieval.assert_awaited_once_with(dataset_id="ds-this")


@pytest.mark.asyncio
async def test_ensure_probe_false_on_supported_ready_chunk_is_unavailable():
    existing = _ready_chunk_state(retrieval_status=IndexRetrievalStatus.unsupported.value)
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=existing)
    kb = SimpleNamespace(id="kb1", org_id="o1")
    adapter = AsyncMock()
    adapter.validate_index_retrieval = AsyncMock(return_value=False)

    with (
        patch(
            "app.services.index_state_service.build_profile_service.resolve_profile_for_kb",
            new=AsyncMock(return_value=SimpleNamespace(index_types=["chunk"])),
        ),
        patch(
            "app.services.index_state_service.list_index_types",
            return_value=[IndexType.chunk.value],
        ),
        patch(
            "app.services.index_state_service.runtime_binding_service.get_dataset_id",
            new=AsyncMock(return_value="ds-this"),
        ),
    ):
        states = await index_state_service.ensure_kb_index_states(
            db,
            org_id="o1",
            kb=kb,
            capabilities={
                "supports_chunk": {"build_supported": True, "retrieval_supported": False},
            },
            runtime_adapter=adapter,
        )

    assert states[0].retrieval_status == IndexRetrievalStatus.unavailable.value


def test_sync_retrieval_status_chunk_supported_not_ready_is_unavailable():
    state = _ready_chunk_state()
    caps = {"supports_chunk": {"build_supported": True, "retrieval_supported": False}}
    index_state_service._sync_retrieval_status(state, IndexType.chunk.value, caps)
    assert state.retrieval_status == IndexRetrievalStatus.unavailable.value


@pytest.mark.asyncio
async def test_apply_chunk_inventory_probe_false_is_unavailable_not_unsupported():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    state = await index_state_service.apply_chunk_inventory(
        db,
        org_id="o1",
        knowledge_base_id="kb1",
        inventory_ready=True,
        retrieval_ready=False,
        summary={"documents_ready": 1},
    )
    assert state.status == IndexStateStatus.ready.value
    assert state.retrieval_status == IndexRetrievalStatus.unavailable.value

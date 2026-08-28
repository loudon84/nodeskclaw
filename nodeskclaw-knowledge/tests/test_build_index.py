"""Build Profile / Index State / Build Job tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.models.enums import BuildJobStatus, IndexStateStatus, IndexType, KnowledgeBaseStatus
from app.services import build_executors, build_orchestrator, build_profile_service, index_registry, index_state_service
from app.services import active_runtime_documents


def _make_job(**overrides):
    defaults = {
        "id": "bj1",
        "org_id": "o1",
        "knowledge_base_id": "kb1",
        "index_type": IndexType.graph.value,
        "status": BuildJobStatus.running.value,
        "progress": 0,
        "error_code": None,
        "error_message": None,
        "stage_results": None,
        "finished_at": None,
        "attempt_count": 1,
        "max_attempts": 5,
        "next_run_at": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_kb(**overrides):
    defaults = {
        "id": "kb1",
        "org_id": "o1",
        "deleted_at": None,
        "status": KnowledgeBaseStatus.active.value,
        "last_error": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_state(**overrides):
    defaults = {
        "status": IndexStateStatus.stale.value,
        "build_version": 0,
        "last_build_job_id": None,
        "last_error": None,
        "last_built_at": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _ready_doc(doc_id: str, chunk_count: int = 5):
    return SimpleNamespace(id=doc_id, run="DONE", chunk_count=chunk_count)


def _pending_doc(doc_id: str):
    return SimpleNamespace(id=doc_id, run="RUNNING", chunk_count=0)


def test_system_profiles_define_standard_enhanced_reasoning():
    assert set(index_registry.SYSTEM_BUILD_PROFILES.keys()) == {
        "standard",
        "enhanced",
        "reasoning",
        "experimental",
    }
    assert IndexType.graph.value not in index_registry.SYSTEM_BUILD_PROFILES["standard"]["index_types"]
    assert IndexType.graph.value in index_registry.SYSTEM_BUILD_PROFILES["reasoning"]["index_types"]
    for spec in index_registry.SYSTEM_BUILD_PROFILES.values():
        assert spec.get("artifact_types") == []
        assert spec.get("artifact_trigger_policy") == {}


def test_unsupported_without_capability():
    assert index_registry.is_runtime_supported(IndexType.chunk.value, {}) is True
    assert index_registry.is_runtime_supported(IndexType.graph.value, {}) is False
    assert index_registry.is_runtime_supported(IndexType.graph.value, {"supports_graph": True}) is True


def test_executors_registry_includes_secondary_indexes():
    assert IndexType.question.value in build_executors.EXECUTORS
    assert IndexType.hierarchical_summary.value in build_executors.EXECUTORS
    assert IndexType.graph.value in build_executors.EXECUTORS


@pytest.mark.asyncio
async def test_ensure_system_profiles_creates_three():
    created: list = []
    keyed: dict = {}

    class FakeDB:
        async def scalar(self, _stmt):
            # build_profile_service queries by system_key; return if already created
            for key, obj in keyed.items():
                # Prefer returning None until all keys filled on first pass
                pass
            return None

        def add(self, obj):
            created.append(obj)
            keyed[obj.system_key] = obj

        async def flush(self):
            return None

    db = FakeDB()

    async def scalar_lookup(_stmt):
        # Without SQL parsing, emulate: if fewer than 3 created, return None so create happens;
        # once 3 exist, still return None would duplicate — so track via created length in ensure.
        # Override ensure to use a keyed check by patching get pattern:
        return None

    # Implement keyed lookup using a counter of attempts per key via add side effects
    attempt = {"i": 0}

    async def smart_scalar(_stmt):
        attempt["i"] += 1
        if len(created) >= 4 and attempt["i"] > 4:
            keys = list(index_registry.SYSTEM_BUILD_PROFILES.keys())
            return keyed.get(keys[(attempt["i"] - 1) % 4])
        return None

    db.scalar = smart_scalar  # type: ignore[method-assign]
    profiles = await build_profile_service.ensure_system_profiles(db)
    assert len(profiles) == 4
    assert {p.system_key for p in profiles} == {"standard", "enhanced", "reasoning", "experimental"}
    assert all(p.is_system for p in profiles)
    assert all((p.artifact_types or []) == [] for p in profiles)
    assert all((p.artifact_trigger_policy or {}) == {} for p in profiles)


@pytest.mark.asyncio
async def test_enqueue_after_activation_marks_stale_when_build_disabled(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V2_BUILD_ENABLED", False)
    db = AsyncMock()
    kb = SimpleNamespace(id="kb1", org_id="o1", active_build_profile_id=None)
    mark = AsyncMock(return_value=[])
    monkeypatch.setattr(index_state_service, "mark_indexes_stale", mark)
    monkeypatch.setattr(
        "app.services.build_input_manifest_service.compute_manifest",
        AsyncMock(return_value=("manifest_hash", [], {"item_count": 0})),
    )
    jobs = await build_orchestrator.enqueue_after_activation(
        db,
        org_id="o1",
        kb=kb,
        source_file_id="sf1",
        version_id="v2",
        capabilities={},
        member_id="m1",
    )
    assert jobs == []
    mark.assert_awaited_once()


@pytest.mark.asyncio
async def test_enqueue_after_activation_enqueues_artifact_jobs(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V2_BUILD_ENABLED", True)
    db = AsyncMock()
    kb = SimpleNamespace(id="kb1", active_build_profile_id=None)
    profile = SimpleNamespace(
        id="bp-standard",
        index_types=["chunk"],
        artifact_types=["table"],
        trigger_policy={"chunk": "ingestion"},
        artifact_trigger_policy={"table": "on_activate"},
    )
    enqueued: list = []

    async def _enqueue_build(*_args, **kwargs):
        enqueued.append(kwargs)
        return SimpleNamespace(id=f"job-{len(enqueued)}")

    monkeypatch.setattr(
        build_profile_service, "resolve_profile_for_kb", AsyncMock(return_value=profile)
    )
    monkeypatch.setattr(index_state_service, "ensure_kb_index_states", AsyncMock(return_value=[]))
    monkeypatch.setattr(index_state_service, "mark_indexes_stale", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        "app.services.build_input_manifest_service.compute_manifest",
        AsyncMock(return_value=("manifest_hash", [], {"item_count": 0})),
    )
    monkeypatch.setattr(build_orchestrator, "enqueue_build", AsyncMock(side_effect=_enqueue_build))

    jobs = await build_orchestrator.enqueue_after_activation(
        db,
        org_id="o1",
        kb=kb,
        source_file_id="sf1",
        version_id="v2",
        capabilities={},
        member_id="m1",
    )
    assert len(jobs) == 1
    assert enqueued[0]["target_kind"] == "artifact"
    assert enqueued[0]["target_key"] == "table"


@pytest.mark.asyncio
async def test_enqueue_after_activation_debounces_graph(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V2_BUILD_ENABLED", True)
    db = AsyncMock()
    kb = SimpleNamespace(id="kb1", active_build_profile_id=None)
    profile = SimpleNamespace(
        id="bp-reasoning",
        index_types=["chunk", "question", "hierarchical_summary", "graph"],
        trigger_policy={
            "chunk": "ingestion",
            "question": "on_activate",
            "hierarchical_summary": "debounce",
            "graph": "debounce",
        },
    )
    monkeypatch.setattr(
        build_profile_service, "resolve_profile_for_kb", AsyncMock(return_value=profile)
    )
    monkeypatch.setattr(index_state_service, "ensure_kb_index_states", AsyncMock(return_value=[]))
    monkeypatch.setattr(index_state_service, "mark_indexes_stale", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        "app.services.build_input_manifest_service.compute_manifest",
        AsyncMock(return_value=("manifest_hash", [], {"item_count": 0})),
    )
    monkeypatch.setattr(
        index_registry,
        "is_runtime_supported",
        lambda index_type, caps: index_type
        in {"chunk", "question", "hierarchical_summary", "graph"},
    )

    async def fake_enqueue(db, **kwargs):
        return SimpleNamespace(id=f"job-{kwargs['index_type']}", **kwargs)

    monkeypatch.setattr(build_orchestrator, "enqueue_build", fake_enqueue)
    jobs = await build_orchestrator.enqueue_after_activation(
        db,
        org_id="o1",
        kb=kb,
        source_file_id="sf1",
        version_id="v2",
        capabilities={
            "supports_graph": True,
            "supports_raptor": True,
            "supports_auto_questions": True,
        },
        member_id="m1",
    )
    by_type = {j.index_type: j for j in jobs}
    assert "question" in by_type
    assert getattr(by_type["question"], "delay_seconds", 0) == 0
    assert "graph" in by_type
    assert by_type["graph"].delay_seconds == 600
    assert "hierarchical_summary" in by_type
    assert by_type["hierarchical_summary"].delay_seconds == 300


@pytest.mark.asyncio
async def test_process_build_job_marks_unsupported_without_public_api(monkeypatch):
    db = AsyncMock()
    kb = _make_kb()
    db.get = AsyncMock(return_value=kb)
    state = _make_state()
    set_status = AsyncMock(return_value=state)
    monkeypatch.setattr(index_state_service, "get_or_create_state", AsyncMock(return_value=state))
    monkeypatch.setattr(index_state_service, "set_state_status", set_status)
    monkeypatch.setattr(
        build_orchestrator.runtime_binding_service,
        "get_binding",
        AsyncMock(return_value=SimpleNamespace(capabilities={})),
    )

    job = _make_job(index_type=IndexType.graph.value)
    await build_orchestrator.process_build_job(db, job)
    assert job.status == BuildJobStatus.completed.value
    assert job.stage_results["status"] == "unsupported"
    assert job.stage_results["stage"] == IndexType.graph.value
    set_status.assert_awaited()


@pytest.mark.asyncio
async def test_process_build_job_chunk_success_restores_degraded_kb(monkeypatch):
    db = AsyncMock()
    kb = _make_kb(status=KnowledgeBaseStatus.degraded.value, last_error="chunk failed")
    db.get = AsyncMock(return_value=kb)
    state = _make_state()
    monkeypatch.setattr(index_state_service, "get_or_create_state", AsyncMock(return_value=state))
    monkeypatch.setattr(index_state_service, "set_state_status", AsyncMock(return_value=state))
    monkeypatch.setattr(
        "app.services.build_input_manifest_service.compute_manifest",
        AsyncMock(return_value=("manifest_hash", [], {"item_count": 0})),
    )
    monkeypatch.setattr(
        build_orchestrator.runtime_binding_service,
        "get_binding",
        AsyncMock(return_value=SimpleNamespace(capabilities={"supports_chunk": True})),
    )
    async def fake_chunk_stage(*_args, **_kwargs):
        return build_executors.StageResult(
            status="succeeded",
            output={"documents_total": 2, "documents_ready": 2, "chunks_total": 10},
        )

    monkeypatch.setitem(build_executors.EXECUTORS, IndexType.chunk.value, fake_chunk_stage)

    job = _make_job(index_type=IndexType.chunk.value)
    await build_orchestrator.process_build_job(db, job)
    assert job.status == BuildJobStatus.completed.value
    assert job.stage_results["status"] == "succeeded"
    assert job.stage_results["output"]["documents_ready"] == 2
    assert kb.status == KnowledgeBaseStatus.active.value
    assert kb.last_error is None


@pytest.mark.asyncio
async def test_process_build_job_chunk_not_ready_requeues(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_BUILD_MAX_ATTEMPTS", 3)
    db = AsyncMock()
    kb = _make_kb()
    db.get = AsyncMock(return_value=kb)
    state = _make_state()
    monkeypatch.setattr(index_state_service, "get_or_create_state", AsyncMock(return_value=state))
    monkeypatch.setattr(index_state_service, "set_state_status", AsyncMock(return_value=state))
    monkeypatch.setattr(
        build_orchestrator.runtime_binding_service,
        "get_binding",
        AsyncMock(return_value=SimpleNamespace(capabilities={"supports_chunk": True})),
    )
    async def fake_chunk_stage(*_args, **_kwargs):
        return build_executors.StageResult(
            status="failed",
            retryable=True,
            error_code="documents_not_ready",
            error_message="1 document(s) not ready",
            output={"not_ready_document_ids": ["d1"]},
        )

    monkeypatch.setitem(build_executors.EXECUTORS, IndexType.chunk.value, fake_chunk_stage)

    job = _make_job(index_type=IndexType.chunk.value, attempt_count=1)
    await build_orchestrator.process_build_job(db, job)
    assert job.status == BuildJobStatus.queued.value
    assert job.next_run_at is not None
    assert job.finished_at is None
    assert job.stage_results["output"]["retry_scheduled"] is True


@pytest.mark.asyncio
async def test_process_build_job_chunk_max_attempts_marks_kb_degraded(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_BUILD_MAX_ATTEMPTS", 3)
    db = AsyncMock()
    kb = _make_kb()
    db.get = AsyncMock(return_value=kb)
    state = _make_state()
    monkeypatch.setattr(index_state_service, "get_or_create_state", AsyncMock(return_value=state))
    monkeypatch.setattr(index_state_service, "set_state_status", AsyncMock(return_value=state))
    monkeypatch.setattr(
        build_orchestrator.runtime_binding_service,
        "get_binding",
        AsyncMock(return_value=SimpleNamespace(capabilities={"supports_chunk": True})),
    )
    async def fake_chunk_stage(*_args, **_kwargs):
        return build_executors.StageResult(
            status="failed",
            retryable=True,
            error_code="documents_not_ready",
            error_message="1 document(s) not ready",
        )

    monkeypatch.setitem(build_executors.EXECUTORS, IndexType.chunk.value, fake_chunk_stage)

    job = _make_job(index_type=IndexType.chunk.value, attempt_count=3)
    await build_orchestrator.process_build_job(db, job)
    assert job.status == BuildJobStatus.failed.value
    assert kb.status == KnowledgeBaseStatus.degraded.value
    assert kb.last_error == "1 document(s) not ready"


@pytest.mark.asyncio
async def test_process_build_job_runs_registered_question_executor(monkeypatch):
    db = AsyncMock()
    kb = _make_kb()
    db.get = AsyncMock(return_value=kb)
    state = _make_state(status=IndexStateStatus.not_built.value)
    set_status = AsyncMock(return_value=state)
    monkeypatch.setattr(index_state_service, "get_or_create_state", AsyncMock(return_value=state))
    monkeypatch.setattr(index_state_service, "set_state_status", set_status)
    monkeypatch.setattr(
        "app.services.build_input_manifest_service.compute_manifest",
        AsyncMock(return_value=("manifest_hash", [], {"item_count": 0})),
    )
    monkeypatch.setattr(
        build_orchestrator.runtime_binding_service,
        "get_binding",
        AsyncMock(
            return_value=SimpleNamespace(
                capabilities={"supports_auto_questions": {"build_supported": True}},
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.reconciliation_service.reconcile_binding_config",
        AsyncMock(return_value={"status": "success", "config_revision": 1, "drift_status": "in_sync", "applied": False}),
    )
    monkeypatch.setattr("app.runtime.ragflow.RagflowRuntimeAdapter", lambda: AsyncMock(aclose=AsyncMock()))

    async def fake_question_stage(_db, _job, _kb):
        return build_executors.StageResult(status="succeeded", output={"documents_ready": 1})

    monkeypatch.setitem(build_executors.EXECUTORS, IndexType.question.value, fake_question_stage)

    job = _make_job(index_type=IndexType.question.value)
    await build_orchestrator.process_build_job(db, job)
    assert job.status == BuildJobStatus.completed.value
    assert job.stage_results["status"] == "succeeded"


@pytest.mark.asyncio
async def test_process_build_job_exception_requeues(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_BUILD_MAX_ATTEMPTS", 3)
    db = AsyncMock()
    kb = _make_kb()
    db.get = AsyncMock(return_value=kb)
    state = _make_state()
    monkeypatch.setattr(index_state_service, "get_or_create_state", AsyncMock(return_value=state))
    monkeypatch.setattr(index_state_service, "set_state_status", AsyncMock(return_value=state))
    monkeypatch.setattr(
        build_orchestrator.runtime_binding_service,
        "get_binding",
        AsyncMock(return_value=SimpleNamespace(capabilities={"supports_chunk": True})),
    )

    async def boom(*_args, **_kwargs):
        raise RuntimeError("ragflow timeout")

    monkeypatch.setitem(build_executors.EXECUTORS, IndexType.chunk.value, boom)

    job = _make_job(index_type=IndexType.chunk.value, attempt_count=1)
    await build_orchestrator.process_build_job(db, job)
    assert job.status == BuildJobStatus.queued.value
    assert job.next_run_at is not None
    assert job.stage_results["error_code"] == "stage_exception"


@pytest.mark.asyncio
async def test_process_build_job_kb_missing(monkeypatch):
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    job = _make_job()
    await build_orchestrator.process_build_job(db, job)
    assert job.status == BuildJobStatus.failed.value
    assert job.error_code == "kb_missing"


@pytest.mark.asyncio
async def test_execute_chunk_stage_succeeds_when_all_documents_ready(monkeypatch):
    db = AsyncMock()
    kb = _make_kb()
    job = _make_job(index_type=IndexType.chunk.value)

    class FakeRagflow:
        async def list_documents(self, _dataset_id, *, page=1, page_size=100, **kwargs):
            if page == 1:
                return [_ready_doc("d1", 3), _ready_doc("d2", 7)]
            return []

        async def aclose(self):
            return None

    monkeypatch.setattr(
        build_executors.runtime_binding_service,
        "require_dataset_id",
        AsyncMock(return_value="ds1"),
    )
    monkeypatch.setattr(build_executors, "_validate_input_manifest", AsyncMock(return_value=None))
    monkeypatch.setattr(build_executors, "RagflowRuntimeAdapter", lambda: FakeRagflow())

    result = await build_executors.execute_chunk_stage(db, job, kb)
    assert result.status == "succeeded"
    assert result.output["documents_total"] == 2
    assert result.output["documents_ready"] == 2
    assert result.output["chunks_total"] == 10


@pytest.mark.asyncio
async def test_execute_chunk_stage_retryable_when_documents_pending(monkeypatch):
    db = AsyncMock()
    kb = _make_kb()
    job = _make_job(index_type=IndexType.chunk.value)

    class FakeRagflow:
        async def list_documents(self, _dataset_id, *, page=1, page_size=100, **kwargs):
            return [_ready_doc("d1"), _pending_doc("d2")]

        async def aclose(self):
            return None

    monkeypatch.setattr(
        build_executors.runtime_binding_service,
        "require_dataset_id",
        AsyncMock(return_value="ds1"),
    )
    monkeypatch.setattr(build_executors, "_validate_input_manifest", AsyncMock(return_value=None))
    monkeypatch.setattr(build_executors, "RagflowRuntimeAdapter", lambda: FakeRagflow())

    result = await build_executors.execute_chunk_stage(db, job, kb)
    assert result.status == "failed"
    assert result.retryable is True
    assert result.error_code == "documents_not_ready"


def test_iter_document_batches_respects_batch_size(monkeypatch):
    from app.services.active_runtime_documents import iter_document_batches

    monkeypatch.setattr(settings, "RAGFLOW_BUILD_BATCH_SIZE", 50)
    ids = [f"d{i}" for i in range(120)]
    batches = iter_document_batches(ids, batch_size=50)
    assert len(batches) == 3
    assert len(batches[0]) == 50
    assert len(batches[2]) == 20


@pytest.mark.asyncio
async def test_resolve_active_documents_returns_active_versions(monkeypatch):
    from app.services import active_runtime_documents

    sf = SimpleNamespace(id="sf1")
    version = SimpleNamespace(id="v1", ragflow_document_id="doc1")
    row = (sf, version)
    result_mock = MagicMock()
    result_mock.all.return_value = [row]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_mock)

    resolution = await active_runtime_documents.resolve_active_documents(db, "kb1")
    assert len(resolution.documents) == 1
    assert resolution.documents[0].ragflow_document_id == "doc1"


@pytest.mark.asyncio
async def test_execute_question_stage_fails_without_enrichment(monkeypatch):
    from app.services import active_runtime_documents

    db = AsyncMock()
    kb = _make_kb()
    job = _make_job(index_type=IndexType.question.value)
    doc = active_runtime_documents.ActiveRuntimeDocument(
        source_file_id="sf1",
        file_version_id="v1",
        ragflow_document_id="d1",
    )
    resolution = active_runtime_documents.ActiveDocumentResolution(documents=[doc])

    class FakeAdapter:
        async def get_index_build_status(self, _dataset_id, _doc_id):
            return {"run": "DONE", "chunk_count": 3}

        async def trigger_index_build(self, *_args, **_kwargs):
            return None

        async def read_document_chunks(self, *_args, **_kwargs):
            return [{"content": "plain chunk"}]

        async def iter_document_chunks(self, *_args, **_kwargs):
            async def _gen():
                yield {"content": "plain chunk"}

            async for item in _gen():
                yield item

        client = SimpleNamespace()

        async def aclose(self):
            return None

    monkeypatch.setattr(
        build_executors.runtime_binding_service,
        "get_binding",
        AsyncMock(return_value=SimpleNamespace(capabilities={"supports_auto_questions": {"build_supported": True}})),
    )
    monkeypatch.setattr(
        build_executors.runtime_binding_service,
        "require_dataset_id",
        AsyncMock(return_value="ds1"),
    )
    monkeypatch.setattr(build_executors, "_validate_input_manifest", AsyncMock(return_value=None))
    monkeypatch.setattr(
        build_executors.index_state_service,
        "get_or_create_state",
        AsyncMock(return_value=SimpleNamespace(input_manifest_summary=None, input_manifest_hash=None)),
    )
    monkeypatch.setattr(
        "app.services.build_input_manifest_service.compute_manifest",
        AsyncMock(return_value=("manifest_hash", [], {"item_count": 0, "items": []})),
    )
    monkeypatch.setattr(
        active_runtime_documents,
        "resolve_and_validate_active_documents",
        AsyncMock(return_value=resolution),
    )
    monkeypatch.setattr(build_executors, "RagflowRuntimeAdapter", lambda: FakeAdapter())

    result = await build_executors.execute_question_stage(db, job, kb)
    assert result.status == "failed"
    assert result.error_code == "artifact_validation_failed"
    assert result.validation_payload is not None
    assert result.validation_payload["question_enriched_chunks"] == 0


@pytest.mark.asyncio
async def test_process_build_job_reconciles_before_secondary_execute(monkeypatch):
    db = AsyncMock()
    kb = _make_kb()
    db.get = AsyncMock(return_value=kb)
    state = _make_state(status=IndexStateStatus.not_built.value)
    monkeypatch.setattr(index_state_service, "get_or_create_state", AsyncMock(return_value=state))
    monkeypatch.setattr(index_state_service, "set_state_status", AsyncMock(return_value=state))
    monkeypatch.setattr(index_state_service, "persist_validation", AsyncMock(return_value=state))
    monkeypatch.setattr(
        "app.services.build_input_manifest_service.compute_manifest",
        AsyncMock(return_value=("manifest_hash", [], {"item_count": 0})),
    )
    monkeypatch.setattr(
        build_orchestrator.runtime_binding_service,
        "get_binding",
        AsyncMock(
            return_value=SimpleNamespace(
                capabilities={"supports_auto_questions": {"build_supported": True}},
                config_revision=2,
            )
        ),
    )
    reconcile = AsyncMock(return_value={"status": "success", "config_revision": 2, "drift_status": "in_sync", "applied": False})
    monkeypatch.setattr("app.services.reconciliation_service.reconcile_binding_config", reconcile)
    monkeypatch.setattr("app.runtime.ragflow.RagflowRuntimeAdapter", lambda: AsyncMock(aclose=AsyncMock()))

    async def fake_question_stage(_db, _job, _kb):
        return build_executors.StageResult(
            status="succeeded",
            output={"documents_ready": 1},
            validation_payload={"ready": True},
            coverage_payload={"coverage_ratio": 1.0},
        )

    monkeypatch.setitem(build_executors.EXECUTORS, IndexType.question.value, fake_question_stage)

    job = _make_job(index_type=IndexType.question.value)
    await build_orchestrator.process_build_job(db, job)
    reconcile.assert_awaited_once()
    assert job.status == BuildJobStatus.completed.value
    assert job.stage_results["output"]["config_reconcile"]["drift_status"] == "in_sync"


@pytest.mark.asyncio
async def test_validate_question_artifacts_paginates_all_chunks():
    doc = active_runtime_documents.ActiveRuntimeDocument(
        source_file_id="sf1",
        file_version_id="v1",
        ragflow_document_id="d1",
    )
    pages = [
        [{"content": "plain"}] * 100,
        [{"content": "plain", "questions": ["q1"]}],
    ]
    call_count = {"n": 0}

    class FakeAdapter:
        async def read_document_chunks(self, _dataset_id, _doc_id, *, page=1, page_size=100):
            idx = page - 1
            call_count["n"] += 1
            if idx >= len(pages):
                return []
            return pages[idx]

        async def iter_document_chunks(self, dataset_id, document_id, *, page_size=100, max_chunks=None):
            page = 1
            yielded = 0
            while True:
                batch = await self.read_document_chunks(dataset_id, document_id, page=page, page_size=page_size)
                if not batch:
                    break
                for chunk in batch:
                    yield chunk
                    yielded += 1
                    if max_chunks is not None and yielded >= max_chunks:
                        return
                if len(batch) < page_size:
                    break
                page += 1

    validation, coverage, ready = await build_executors._validate_question_artifacts(
        FakeAdapter(), "ds1", [doc]
    )
    assert call_count["n"] == 2
    assert validation["question_enriched_chunks"] == 1
    assert validation["inspected_chunks"] == 101
    assert coverage["document_coverage"] == 1.0
    assert coverage["chunk_coverage"] == pytest.approx(1 / 101)
    assert ready is True


@pytest.mark.asyncio
async def test_validate_graph_artifacts_requires_three_ready_states():
    class FakeAdapter:
        async def get_dataset_graph(self, _dataset_id):
            return {"entities": [{"name": "e1"}], "relations": []}

        async def feature_retrieve(self, **_kwargs):
            return {"chunks": []}

    validation, _coverage, ready = await build_executors._validate_graph_artifacts(FakeAdapter(), "ds1")
    assert validation["build_ready"] is True
    assert validation["retrieval_ready"] is True
    assert validation["lineage_ready"] is False
    assert ready is False


@pytest.mark.asyncio
async def test_validate_summary_artifacts_requires_lineage():
    doc = active_runtime_documents.ActiveRuntimeDocument(
        source_file_id="sf1",
        file_version_id="v1",
        ragflow_document_id="d1",
    )

    class FakeAdapter:
        async def iter_document_chunks(self, *_args, **_kwargs):
            yield {"raptor": True, "content": "summary without lineage"}

    validation, _coverage, ready = await build_executors._validate_summary_artifacts(
        FakeAdapter(), "ds1", [doc]
    )
    assert validation["summary_chunks"] == 1
    assert validation["lineage_valid_chunks"] == 0
    assert validation["build_ready"] is True
    assert validation["lineage_ready"] is False
    assert ready is False


def test_manifest_hash_changes_when_any_active_version_changes():
    from app.services.build_input_manifest_service import ManifestItem, hash_manifest_items

    base = [
        ManifestItem("sf1", "v1", 0, "doc1"),
        ManifestItem("sf2", "v2", 0, "doc2"),
    ]
    changed = [
        ManifestItem("sf1", "v1-new", 0, "doc1"),
        ManifestItem("sf2", "v2", 0, "doc2"),
    ]
    assert hash_manifest_items(base) != hash_manifest_items(changed)


def test_build_delta_reports_single_file_change():
    from app.services.build_input_manifest_service import ManifestItem, compute_build_delta

    previous = [
        ManifestItem("sf1", "v1", 0, "doc1"),
        ManifestItem("sf2", "v2", 0, "doc2"),
    ]
    current = [
        ManifestItem("sf1", "v1-new", 0, "doc1"),
        ManifestItem("sf2", "v2", 0, "doc2"),
    ]
    delta = compute_build_delta(previous, current)
    assert len(delta.changed) == 1
    assert len(delta.unchanged) == 1
    assert delta.changed[0].source_file_id == "sf1"


@pytest.mark.asyncio
async def test_validate_input_manifest_detects_corpus_change(monkeypatch):
    from app.services import build_input_manifest_service

    db = AsyncMock()
    kb = _make_kb()
    state = _make_state()
    state.input_manifest_hash = "expected-hash"
    monkeypatch.setattr(index_state_service, "get_or_create_state", AsyncMock(return_value=state))
    monkeypatch.setattr(
        build_input_manifest_service,
        "compute_manifest",
        AsyncMock(return_value=("other-hash", [], {"item_count": 1})),
    )
    result = await build_executors._validate_input_manifest(db, kb, IndexType.question.value)
    assert result is not None
    assert result.error_code == "input_manifest_mismatch"


@pytest.mark.asyncio
async def test_incremental_build_processes_only_changed_documents(monkeypatch):
    from app.services import active_runtime_documents, build_input_manifest_service

    monkeypatch.setattr(settings, "KNOWLEDGE_V23_INCREMENTAL_BUILD_ENABLED", True)
    db = AsyncMock()
    kb = _make_kb()
    job = _make_job(index_type=IndexType.question.value)
    docs = [
        active_runtime_documents.ActiveRuntimeDocument("sf1", "v1", "d1"),
        active_runtime_documents.ActiveRuntimeDocument("sf2", "v2", "d2"),
    ]
    resolution = active_runtime_documents.ActiveDocumentResolution(documents=docs)
    state = _make_state()
    state.input_manifest_summary = {
        "items": [
            {"source_file_id": "sf1", "file_version_id": "v0", "metadata_revision": 0, "ragflow_document_id": "d1"},
            {"source_file_id": "sf2", "file_version_id": "v2", "metadata_revision": 0, "ragflow_document_id": "d2"},
        ]
    }
    current_items = build_input_manifest_service.items_from_summary(
        {
            "items": [
                {"source_file_id": "sf1", "file_version_id": "v1", "metadata_revision": 0, "ragflow_document_id": "d1"},
                {"source_file_id": "sf2", "file_version_id": "v2", "metadata_revision": 0, "ragflow_document_id": "d2"},
            ]
        }
    )

    class FakeAdapter:
        async def get_index_build_status(self, _dataset_id, _doc_id):
            return {"run": "DONE", "chunk_count": 3}

        async def trigger_index_build(self, *_args, **_kwargs):
            return None

        async def iter_document_chunks(self, *_args, **_kwargs):
            yield {"content": "plain chunk", "questions": ["q1"]}

        async def aclose(self):
            return None

    monkeypatch.setattr(
        build_executors.runtime_binding_service,
        "get_binding",
        AsyncMock(return_value=SimpleNamespace(capabilities={"supports_auto_questions": {"build_supported": True}})),
    )
    monkeypatch.setattr(
        build_executors.runtime_binding_service,
        "require_dataset_id",
        AsyncMock(return_value="ds1"),
    )
    monkeypatch.setattr(build_executors, "_validate_input_manifest", AsyncMock(return_value=None))
    monkeypatch.setattr(index_state_service, "get_or_create_state", AsyncMock(return_value=state))
    monkeypatch.setattr(
        build_input_manifest_service,
        "compute_manifest",
        AsyncMock(return_value=("hash", current_items, {"item_count": 2})),
    )
    monkeypatch.setattr(
        active_runtime_documents,
        "resolve_and_validate_active_documents",
        AsyncMock(return_value=resolution),
    )
    monkeypatch.setattr(build_executors, "RagflowRuntimeAdapter", lambda: FakeAdapter())

    result = await build_executors.execute_question_stage(db, job, kb)
    assert result.status == "succeeded"
    assert result.output["incremental_build"] is True
    assert result.output["processed_document_count"] == 1
    assert result.output["build_delta"]["changed"] == 1


@pytest.mark.asyncio
async def test_incremental_build_noop_when_corpus_unchanged(monkeypatch):
    from app.services import active_runtime_documents, build_input_manifest_service
    from app.services.build_input_manifest_service import ManifestItem

    monkeypatch.setattr(settings, "KNOWLEDGE_V23_INCREMENTAL_BUILD_ENABLED", True)
    db = AsyncMock()
    kb = _make_kb()
    job = _make_job(index_type=IndexType.question.value)
    docs = [
        active_runtime_documents.ActiveRuntimeDocument("sf1", "v1", "d1"),
    ]
    resolution = active_runtime_documents.ActiveDocumentResolution(documents=docs)
    items = [
        ManifestItem("sf1", "v1", 0, "d1"),
    ]
    state = _make_state()
    state.input_manifest_summary = {
        "items": [
            {"source_file_id": "sf1", "file_version_id": "v1", "metadata_revision": 0, "ragflow_document_id": "d1"},
        ]
    }

    trigger_parse = AsyncMock()
    monkeypatch.setattr(build_executors, "_trigger_parse_batches", trigger_parse)
    monkeypatch.setattr(
        build_executors.runtime_binding_service,
        "get_binding",
        AsyncMock(return_value=SimpleNamespace(capabilities={"supports_auto_questions": {"build_supported": True}})),
    )
    monkeypatch.setattr(
        build_executors.runtime_binding_service,
        "require_dataset_id",
        AsyncMock(return_value="ds1"),
    )
    monkeypatch.setattr(build_executors, "_validate_input_manifest", AsyncMock(return_value=None))
    monkeypatch.setattr(index_state_service, "get_or_create_state", AsyncMock(return_value=state))
    monkeypatch.setattr(
        build_input_manifest_service,
        "compute_manifest",
        AsyncMock(return_value=("hash", items, {"item_count": 1})),
    )
    monkeypatch.setattr(
        active_runtime_documents,
        "resolve_and_validate_active_documents",
        AsyncMock(return_value=resolution),
    )
    monkeypatch.setattr(build_executors, "RagflowRuntimeAdapter", lambda: SimpleNamespace(aclose=AsyncMock()))

    result = await build_executors.execute_question_stage(db, job, kb)
    assert result.status == "succeeded"
    assert result.output["incremental_noop"] is True
    assert result.output["processed_document_count"] == 0
    trigger_parse.assert_not_called()


@pytest.mark.asyncio
async def test_incremental_build_removal_only_updates_without_rebuild(monkeypatch):
    from app.services import active_runtime_documents, build_input_manifest_service
    from app.services.build_input_manifest_service import ManifestItem

    monkeypatch.setattr(settings, "KNOWLEDGE_V23_INCREMENTAL_BUILD_ENABLED", True)
    db = AsyncMock()
    kb = _make_kb()
    job = _make_job(index_type=IndexType.question.value)
    docs = [
        active_runtime_documents.ActiveRuntimeDocument("sf1", "v1", "d1"),
    ]
    resolution = active_runtime_documents.ActiveDocumentResolution(documents=docs)
    previous_items = [
        ManifestItem("sf1", "v1", 0, "d1"),
        ManifestItem("sf2", "v2", 0, "d2"),
    ]
    current_items = [
        ManifestItem("sf1", "v1", 0, "d1"),
    ]
    state = _make_state()
    state.input_manifest_summary = {
        "items": [
            {"source_file_id": "sf1", "file_version_id": "v1", "metadata_revision": 0, "ragflow_document_id": "d1"},
            {"source_file_id": "sf2", "file_version_id": "v2", "metadata_revision": 0, "ragflow_document_id": "d2"},
        ]
    }

    trigger_parse = AsyncMock()
    monkeypatch.setattr(build_executors, "_trigger_parse_batches", trigger_parse)
    monkeypatch.setattr(
        build_executors.runtime_binding_service,
        "get_binding",
        AsyncMock(return_value=SimpleNamespace(capabilities={"supports_auto_questions": {"build_supported": True}})),
    )
    monkeypatch.setattr(
        build_executors.runtime_binding_service,
        "require_dataset_id",
        AsyncMock(return_value="ds1"),
    )
    monkeypatch.setattr(build_executors, "_validate_input_manifest", AsyncMock(return_value=None))
    monkeypatch.setattr(index_state_service, "get_or_create_state", AsyncMock(return_value=state))
    monkeypatch.setattr(
        build_input_manifest_service,
        "compute_manifest",
        AsyncMock(return_value=("hash", current_items, {"item_count": 1})),
    )
    monkeypatch.setattr(
        active_runtime_documents,
        "resolve_and_validate_active_documents",
        AsyncMock(return_value=resolution),
    )
    monkeypatch.setattr(build_executors, "RagflowRuntimeAdapter", lambda: SimpleNamespace(aclose=AsyncMock()))

    result = await build_executors.execute_question_stage(db, job, kb)
    assert result.status == "succeeded"
    assert result.output["incremental_removal_only"] is True
    assert result.output["processed_document_count"] == 0
    assert result.output["build_delta"]["removed"] == 1
    trigger_parse.assert_not_called()


@pytest.mark.asyncio
async def test_enqueue_build_pins_knowledge_model_revision_id(monkeypatch):
    from app.services import build_orchestrator

    db = AsyncMock()
    kb = _make_kb()
    kb.knowledge_model_id = "model-1"
    db.get = AsyncMock(return_value=kb)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    monkeypatch.setattr(
        build_orchestrator,
        "_resolve_active_model_revision_id",
        AsyncMock(return_value="rev-1"),
    )

    job = await build_orchestrator.enqueue_build(
        db,
        org_id="org-1",
        knowledge_base_id=kb.id,
        index_type=IndexType.question.value,
        trigger_reason="manual",
    )
    assert job.knowledge_model_revision_id == "rev-1"

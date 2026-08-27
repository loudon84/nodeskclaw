"""Build Profile / Index State / Build Job tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.models.enums import BuildJobStatus, IndexStateStatus, IndexType, KnowledgeBaseStatus
from app.services import build_executors, build_orchestrator, build_profile_service, index_registry, index_state_service


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


@pytest.mark.asyncio
async def test_enqueue_after_activation_marks_stale_when_build_disabled(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V2_BUILD_ENABLED", False)
    db = AsyncMock()
    kb = SimpleNamespace(id="kb1", active_build_profile_id=None)
    mark = AsyncMock(return_value=[])
    monkeypatch.setattr(index_state_service, "mark_indexes_stale", mark)
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
        build_orchestrator.runtime_binding_service,
        "get_binding",
        AsyncMock(
            return_value=SimpleNamespace(
                capabilities={"supports_auto_questions": {"build_supported": True}},
            )
        ),
    )

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
    monkeypatch.setattr(build_executors, "_validate_source_watermark", AsyncMock(return_value=None))
    monkeypatch.setattr(build_executors, "RagflowClient", lambda: FakeRagflow())

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
    monkeypatch.setattr(build_executors, "_validate_source_watermark", AsyncMock(return_value=None))
    monkeypatch.setattr(build_executors, "RagflowClient", lambda: FakeRagflow())

    result = await build_executors.execute_chunk_stage(db, job, kb)
    assert result.status == "failed"
    assert result.retryable is True
    assert result.error_code == "documents_not_ready"

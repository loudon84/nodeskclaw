"""Build Profile / Index State / Build Job tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.models.enums import BuildJobStatus, IndexStateStatus, IndexType
from app.services import build_orchestrator, build_profile_service, index_registry, index_state_service


def test_system_profiles_define_standard_enhanced_reasoning():
    assert set(index_registry.SYSTEM_BUILD_PROFILES.keys()) == {"standard", "enhanced", "reasoning"}
    assert IndexType.graph.value not in index_registry.SYSTEM_BUILD_PROFILES["standard"]["index_types"]
    assert IndexType.graph.value in index_registry.SYSTEM_BUILD_PROFILES["reasoning"]["index_types"]


def test_unsupported_without_capability():
    assert index_registry.is_runtime_supported(IndexType.chunk.value, {}) is True
    assert index_registry.is_runtime_supported(IndexType.graph.value, {}) is False
    assert index_registry.is_runtime_supported(IndexType.graph.value, {"supports_graph": True}) is True


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
        # Calls 1,2,3: miss; if somehow more before add, still miss until add
        # After objects exist, subsequent ensure calls should hit — we only run once here
        if len(created) >= 3 and attempt["i"] > 3:
            keys = list(index_registry.SYSTEM_BUILD_PROFILES.keys())
            return keyed.get(keys[(attempt["i"] - 1) % 3])
        return None

    db.scalar = smart_scalar  # type: ignore[method-assign]
    profiles = await build_profile_service.ensure_system_profiles(db)
    assert len(profiles) == 3
    assert {p.system_key for p in profiles} == {"standard", "enhanced", "reasoning"}
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
    kb = SimpleNamespace(id="kb1", deleted_at=None)
    db.get = AsyncMock(return_value=kb)
    state = SimpleNamespace(
        status=IndexStateStatus.stale.value,
        build_version=0,
        last_build_job_id=None,
        last_error=None,
        last_built_at=None,
    )
    set_status = AsyncMock(return_value=state)
    monkeypatch.setattr(index_state_service, "get_or_create_state", AsyncMock(return_value=state))
    monkeypatch.setattr(index_state_service, "set_state_status", set_status)

    job = SimpleNamespace(
        id="bj1",
        org_id="o1",
        knowledge_base_id="kb1",
        index_type=IndexType.graph.value,
        status=BuildJobStatus.running.value,
        progress=0,
        error_code=None,
        error_message=None,
        stage_results=None,
        finished_at=None,
        attempt_count=1,
    )
    await build_orchestrator.process_build_job(db, job)
    assert job.status == BuildJobStatus.completed.value
    assert job.stage_results["result"] == "unsupported"
    set_status.assert_awaited()

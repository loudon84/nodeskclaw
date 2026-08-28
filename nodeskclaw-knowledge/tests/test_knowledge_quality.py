"""Knowledge quality API/service tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_quality_service


MEMBER = KnowledgePrincipal(
    user_id="user-1",
    member_id="member-1",
    org_id="org-1",
    name="Tester",
)


@pytest.mark.asyncio
async def test_runtime_snapshot_excludes_dataset_id(monkeypatch):
    app = SimpleNamespace(
        id="app-1",
        active_profile_id="profile-1",
        acl_version=2,
    )
    kb = SimpleNamespace(id="kb-1")
    binding = SimpleNamespace(status="ready")
    state = SimpleNamespace(index_type="chunk", status="ready", input_manifest_hash="hash-1")

    db = MagicMock()
    monkeypatch.setattr(
        knowledge_quality_service.knowledge_application_service,
        "list_bound_set_ids",
        AsyncMock(return_value=["set-1"]),
    )
    monkeypatch.setattr(
        knowledge_quality_service.knowledge_set_service,
        "list_bound_knowledge_bases",
        AsyncMock(return_value=[kb]),
    )
    monkeypatch.setattr(
        knowledge_quality_service.runtime_binding_service,
        "get_binding",
        AsyncMock(return_value=binding),
    )
    monkeypatch.setattr(
        knowledge_quality_service.index_state_service,
        "list_states_for_kb",
        AsyncMock(return_value=[state]),
    )

    snapshot = await knowledge_quality_service.build_runtime_snapshot(db, MEMBER, app)
    assert "dataset_id" not in str(snapshot)
    assert snapshot["bound_set_ids"] == ["set-1"]
    assert snapshot["knowledge_bases"][0]["knowledge_base_id"] == "kb-1"


@pytest.mark.asyncio
async def test_kb_quality_binding_score_requires_ready(monkeypatch):
    kb = SimpleNamespace(id="kb-1", org_id="org-1", deleted_at=None)
    db = MagicMock()
    db.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))

    ready_binding = SimpleNamespace(status="ready")
    monkeypatch.setattr(
        knowledge_quality_service.runtime_binding_service,
        "get_binding",
        AsyncMock(return_value=ready_binding),
    )
    monkeypatch.setattr(
        knowledge_quality_service.index_state_service,
        "list_states_for_kb",
        AsyncMock(return_value=[]),
    )

    ready_payload = await knowledge_quality_service._kb_quality(db, kb)
    assert ready_payload["subscores"]["runtime_binding"] == 1.0

    not_ready_binding = SimpleNamespace(status="provisioning")
    monkeypatch.setattr(
        knowledge_quality_service.runtime_binding_service,
        "get_binding",
        AsyncMock(return_value=not_ready_binding),
    )
    not_ready_payload = await knowledge_quality_service._kb_quality(db, kb)
    assert not_ready_payload["subscores"]["runtime_binding"] == 0.0


@pytest.mark.asyncio
async def test_kb_quality_response_shape(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V23_QUALITY_ENABLED", True)
    kb = SimpleNamespace(id="kb-1", org_id="org-1", deleted_at=None)
    db = MagicMock()
    db.get = AsyncMock(return_value=kb)
    monkeypatch.setattr(knowledge_quality_service, "_kb_quality", AsyncMock(return_value={
        "knowledge_base_id": "kb-1",
        "score_status": "partial",
        "subscores": {"runtime_binding": 1.0, "index_readiness": 0.5, "artifact_readiness": None},
        "data_coverage": {"index_state_count": 2},
        "issues": ["index_not_ready"],
        "calculated_at": "2026-01-01T00:00:00+00:00",
    }))
    payload = await knowledge_quality_service.get_kb_quality(db, MEMBER, "kb-1")
    assert payload["score_status"] == "partial"
    assert "subscores" in payload
    assert "data_coverage" in payload


@pytest.mark.asyncio
async def test_evaluate_gate_pass_when_scores_complete():
    payload = {
        "score_status": "complete",
        "subscores": {"runtime_binding": 1.0, "index_readiness": 1.0, "artifact_readiness": 1.0},
        "issues": [],
    }
    gate_result, _ = knowledge_quality_service.evaluate_gate(payload)
    assert gate_result == "PASS"


@pytest.mark.asyncio
async def test_evaluate_gate_fail_when_binding_inactive():
    payload = {
        "score_status": "partial",
        "subscores": {"runtime_binding": 0.0},
        "issues": ["runtime_binding_inactive"],
    }
    gate_result, details = knowledge_quality_service.evaluate_gate(payload)
    assert gate_result == "FAIL"
    assert details["checks"]["fail_reasons"]

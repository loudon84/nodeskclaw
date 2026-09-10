"""Knowledge quality API/service tests."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.core.exceptions import ConflictError
from app.models.enums import ApplicationReleaseStatus, QualityGateResult, QualitySnapshotScopeType
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_quality_service, release_integrity_service, release_promotion_service


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


@pytest.mark.asyncio
async def test_get_application_quality_does_not_persist_snapshot(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V23_QUALITY_ENABLED", True)
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    app = SimpleNamespace(id="app-1", runtime_snapshot=None)
    db = MagicMock()
    monkeypatch.setattr(
        knowledge_quality_service.knowledge_application_service,
        "get_application",
        AsyncMock(return_value=app),
    )
    monkeypatch.setattr(
        knowledge_quality_service,
        "_compute_application_quality",
        AsyncMock(return_value={
            "application_id": "app-1",
            "score_status": "complete",
            "subscores": {"runtime_binding": 1.0},
            "data_coverage": {},
            "issues": [],
            "calculated_at": "2026-01-01T00:00:00+00:00",
        }),
    )
    persist_mock = AsyncMock()
    monkeypatch.setattr(knowledge_quality_service, "persist_application_snapshot", persist_mock)

    payload = await knowledge_quality_service.get_application_quality(db, MEMBER, "app-1")

    assert payload["application_id"] == "app-1"
    persist_mock.assert_not_called()
    db.commit.assert_not_called()


def _release_context():
    return SimpleNamespace(
        release_id="rel-1",
        application_id="app-1",
        channel="evaluation",
        manifest_hash="hash-pin",
        knowledge_set_ids=["set-pin"],
        knowledge_bases=[{"knowledge_base_id": "kb-pin", "knowledge_set_id": "set-pin"}],
    )


@pytest.mark.asyncio
async def test_release_quality_uses_execution_context_pins_not_live_binds(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V23_QUALITY_ENABLED", True)
    db = MagicMock()
    live_bind = AsyncMock(side_effect=AssertionError("live application bindings must not be quality authority"))
    monkeypatch.setattr(
        knowledge_quality_service.knowledge_application_service,
        "list_bound_set_ids",
        live_bind,
    )
    monkeypatch.setattr(
        knowledge_quality_service,
        "resolve_evaluation_release",
        AsyncMock(return_value=_release_context()),
    )
    monkeypatch.setattr(
        knowledge_quality_service.knowledge_application_service,
        "get_application",
        AsyncMock(return_value=SimpleNamespace(id="app-1")),
    )
    monkeypatch.setattr(
        knowledge_quality_service,
        "get_knowledge_base",
        AsyncMock(return_value=SimpleNamespace(id="kb-pin")),
    )
    monkeypatch.setattr(
        knowledge_quality_service,
        "_kb_quality",
        AsyncMock(
            return_value={
                "knowledge_base_id": "kb-pin",
                "subscores": {"runtime_binding": 1.0, "index_readiness": 1.0, "artifact_readiness": 1.0},
                "issues": [],
            }
        ),
    )

    payload = await knowledge_quality_service.get_release_quality(db, MEMBER, "rel-1")

    live_bind.assert_not_called()
    assert payload["release_id"] == "rel-1"
    assert payload["data_coverage"]["knowledge_set_ids"] == ["set-pin"]
    assert payload["data_coverage"]["source"] == "execution_context"
    assert payload["data_coverage"]["knowledge_bases"] == [
        {"knowledge_base_id": "kb-pin", "knowledge_set_id": "set-pin"}
    ]


@pytest.mark.asyncio
async def test_persist_release_snapshot_scope_is_application_release(monkeypatch):
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    monkeypatch.setattr(
        knowledge_quality_service,
        "resolve_evaluation_release",
        AsyncMock(return_value=_release_context()),
    )
    monkeypatch.setattr(
        knowledge_quality_service.knowledge_application_service,
        "get_application",
        AsyncMock(return_value=SimpleNamespace(id="app-1")),
    )
    monkeypatch.setattr(
        knowledge_quality_service,
        "get_gate_policy",
        AsyncMock(return_value=dict(knowledge_quality_service.DEFAULT_GATE_POLICY)),
    )
    monkeypatch.setattr(
        knowledge_quality_service,
        "_compute_release_quality",
        AsyncMock(
            return_value={
                "application_id": "app-1",
                "release_id": "rel-1",
                "score_status": "complete",
                "subscores": {"runtime_binding": 1.0, "index_readiness": 1.0, "artifact_readiness": 1.0},
                "data_coverage": {
                    "knowledge_set_ids": ["set-pin"],
                    "knowledge_bases": [{"knowledge_base_id": "kb-pin", "knowledge_set_id": "set-pin"}],
                    "source": "execution_context",
                },
                "issues": [],
            }
        ),
    )

    snapshot = await knowledge_quality_service.persist_release_snapshot(db, MEMBER, "rel-1")

    assert snapshot.scope_type == "application_release"
    assert snapshot.scope_id == "rel-1"
    assert snapshot.release_id == "rel-1"
    assert snapshot.coverage["knowledge_set_ids"] == ["set-pin"]
    db.add.assert_called_once_with(snapshot)


@pytest.mark.asyncio
async def test_live_rebind_does_not_change_release_snapshot_topology(monkeypatch):
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    live_sets = ["set-pin"]

    async def live_bind(_db, _application_id):
        return list(live_sets)

    monkeypatch.setattr(
        knowledge_quality_service.knowledge_application_service,
        "list_bound_set_ids",
        live_bind,
    )
    monkeypatch.setattr(
        knowledge_quality_service,
        "resolve_evaluation_release",
        AsyncMock(return_value=_release_context()),
    )
    monkeypatch.setattr(
        knowledge_quality_service.knowledge_application_service,
        "get_application",
        AsyncMock(return_value=SimpleNamespace(id="app-1", runtime_snapshot=None)),
    )
    monkeypatch.setattr(
        knowledge_quality_service,
        "get_gate_policy",
        AsyncMock(return_value=dict(knowledge_quality_service.DEFAULT_GATE_POLICY)),
    )
    monkeypatch.setattr(
        knowledge_quality_service,
        "get_knowledge_base",
        AsyncMock(return_value=SimpleNamespace(id="kb-pin")),
    )
    monkeypatch.setattr(
        knowledge_quality_service,
        "_kb_quality",
        AsyncMock(
            return_value={
                "knowledge_base_id": "kb-pin",
                "subscores": {"runtime_binding": 1.0, "index_readiness": 1.0, "artifact_readiness": 1.0},
                "issues": [],
            }
        ),
    )
    monkeypatch.setattr(
        knowledge_quality_service.knowledge_set_service,
        "list_bound_knowledge_bases",
        AsyncMock(return_value=[]),
    )

    first = await knowledge_quality_service.persist_release_snapshot(db, MEMBER, "rel-1")
    live_sets[:] = ["set-live"]
    second = await knowledge_quality_service.persist_release_snapshot(db, MEMBER, "rel-1")
    live_payload = await knowledge_quality_service._compute_application_quality(
        db,
        MEMBER,
        "app-1",
        SimpleNamespace(id="app-1", runtime_snapshot=None),
    )

    assert first.coverage["knowledge_set_ids"] == ["set-pin"]
    assert second.coverage["knowledge_set_ids"] == ["set-pin"]
    assert first.coverage["knowledge_bases"] == second.coverage["knowledge_bases"]
    assert live_payload["data_coverage"]["bound_set_count"] == 1


def test_default_gate_policy_omits_evaluation_required():
    assert "evaluation.required" not in knowledge_quality_service.DEFAULT_GATE_POLICY
    assert "evaluation_required" not in knowledge_quality_service.DEFAULT_GATE_POLICY


def test_evaluate_gate_evaluation_required_missing_is_not_pass():
    payload = {
        "score_status": "complete",
        "subscores": {"runtime_binding": 1.0, "index_readiness": 1.0, "artifact_readiness": 1.0},
        "issues": [],
    }
    default_result, _ = knowledge_quality_service.evaluate_gate(payload)
    assert default_result == "PASS"
    required_result, details = knowledge_quality_service.evaluate_gate(
        payload,
        policy={"evaluation.required": True},
    )
    assert required_result == "FAIL"
    assert "evaluation_required_missing" in details["checks"]["fail_reasons"]


@pytest.mark.asyncio
async def test_promote_stable_rejects_live_only_application_snapshot(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    release = SimpleNamespace(
        id="rel-1",
        org_id="org-1",
        application_id="app-1",
        version=1,
        status=ApplicationReleaseStatus.validated.value,
        release_manifest={"application_id": "app-1"},
        manifest_hash="hash-1",
        quality_snapshot_id="snap-live",
        promoted_at=None,
        deleted_at=None,
    )
    snapshot = SimpleNamespace(
        id="snap-live",
        deleted_at=None,
        gate_result=QualityGateResult.pass_.value,
        manifest_hash="hash-1",
        calculated_at=datetime.now(UTC),
        scope_type=QualitySnapshotScopeType.application.value,
        scope_id="app-1",
    )
    channel = SimpleNamespace(
        id="ch-1",
        application_id="app-1",
        channel="stable",
        active_release_id=None,
        updated_by_member_id=None,
        updated_at=datetime.now(UTC),
        deleted_at=None,
    )
    db = MagicMock()
    db.get = AsyncMock(return_value=snapshot)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    monkeypatch.setattr(
        release_promotion_service,
        "get_application",
        AsyncMock(return_value=SimpleNamespace(id="app-1", status="draft")),
    )
    monkeypatch.setattr(
        release_promotion_service,
        "has_application_permission",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        release_promotion_service,
        "get_release",
        AsyncMock(return_value=release),
    )
    monkeypatch.setattr(
        release_promotion_service,
        "application_advisory_xact_lock",
        AsyncMock(),
    )
    monkeypatch.setattr(
        release_promotion_service,
        "_get_channel",
        AsyncMock(return_value=channel),
    )
    monkeypatch.setattr(
        release_integrity_service,
        "evaluate",
        AsyncMock(return_value=release_integrity_service.ReleaseIntegrityResult(status="healthy", reasons=[])),
    )

    with pytest.raises(ConflictError) as exc:
        await release_promotion_service.promote(
            db, MEMBER, "app-1", channel="stable", release_id="rel-1"
        )
    assert exc.value.message_key == "errors.knowledge.release_quality_snapshot_live_only"

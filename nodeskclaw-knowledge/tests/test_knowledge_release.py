"""Knowledge Application Release / Channel / Promotion tests."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.core.exceptions import BadRequestError, ConflictError
from app.models.enums import ApplicationReleaseStatus, QualityGateResult
from app.schemas.principal import KnowledgePrincipal
from app.services import (
    knowledge_application_service,
    knowledge_quality_service,
    release_promotion_service,
)


MEMBER = KnowledgePrincipal(
    user_id="user-1",
    member_id="member-1",
    org_id="org-1",
    name="Tester",
)


def _app():
    return SimpleNamespace(
        id="app-1",
        org_id="org-1",
        owner_member_id="member-1",
        deleted_at=None,
        answer_model="gpt-4",
        active_profile_id=None,
        acl_version=1,
        runtime_snapshot=None,
    )


def _release(*, status="draft", version=1, manifest=None, snapshot_id=None):
    return SimpleNamespace(
        id="rel-1",
        org_id="org-1",
        application_id="app-1",
        version=version,
        status=status,
        release_manifest=manifest
        or {
            "application_id": "app-1",
            "release_version": version,
            "retrieval_policy_revision_id": "policy-1",
            "answer_model": "gpt-4",
            "knowledge_sets": [],
        },
        quality_snapshot_id=snapshot_id,
        created_by_member_id="member-1",
        promoted_at=None,
        retired_at=None,
        validation_error=None,
        deleted_at=None,
        created_at=datetime.now(UTC),
    )


def _policy_revision():
    return SimpleNamespace(
        id="policy-1",
        application_id="app-1",
        org_id="org-1",
        deleted_at=None,
        status="active",
    )


def _snapshot(*, gate_result=QualityGateResult.pass_.value):
    return SimpleNamespace(
        id="snap-1",
        deleted_at=None,
        gate_result=gate_result,
    )


@pytest.mark.asyncio
async def test_create_release_requires_policy_revision(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    db = MagicMock()
    db.get = AsyncMock(return_value=None)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with patch(
        "app.services.knowledge_application_service.get_application",
        new=AsyncMock(return_value=_app()),
    ), patch(
        "app.services.knowledge_application_service.has_application_permission",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.application_retrieval_policy_service.get_active_revision",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(BadRequestError) as exc:
            await knowledge_application_service.create_release(db, MEMBER, "app-1")
    assert exc.value.message_key == "errors.knowledge.retrieval_policy_revision_required"


@pytest.mark.asyncio
async def test_create_release_returns_draft(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    app = _app()
    db = MagicMock()
    db.get = AsyncMock(return_value=_policy_revision())
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with patch(
        "app.services.knowledge_application_service.get_application",
        new=AsyncMock(return_value=app),
    ), patch(
        "app.services.knowledge_application_service.has_application_permission",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.application_retrieval_policy_service.get_active_revision",
        new=AsyncMock(return_value=_policy_revision()),
    ), patch(
        "app.services.knowledge_application_service._next_release_version",
        new=AsyncMock(return_value=3),
    ), patch(
        "app.services.knowledge_application_service.build_release_manifest",
        new=AsyncMock(
            return_value={
                "application_id": "app-1",
                "release_version": 3,
                "retrieval_policy_revision_id": "policy-1",
                "answer_model": "gpt-4",
                "knowledge_sets": [],
            }
        ),
    ), patch(
        "app.services.knowledge_application_service.ensure_release_channels",
        new=AsyncMock(return_value=[]),
    ), patch(
        "app.services.knowledge_application_service.write_audit",
        new=AsyncMock(),
    ):
        release = await knowledge_application_service.create_release(db, MEMBER, "app-1")

    assert release.status == ApplicationReleaseStatus.draft.value
    assert release.version == 3
    assert release.release_manifest["retrieval_policy_revision_id"] == "policy-1"


@pytest.mark.asyncio
async def test_validate_release_sets_validated_on_pass(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    release = _release(status=ApplicationReleaseStatus.draft.value)
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    readiness = SimpleNamespace(ready=True, to_dict=lambda: {"ready": True})
    snapshot = _snapshot(gate_result=QualityGateResult.pass_.value)

    with patch(
        "app.services.knowledge_application_service.get_application",
        new=AsyncMock(return_value=_app()),
    ), patch(
        "app.services.knowledge_application_service.has_application_permission",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.knowledge_application_service.get_release",
        new=AsyncMock(return_value=release),
    ), patch(
        "app.services.application_readiness_service.check",
        new=AsyncMock(return_value=readiness),
    ), patch(
        "app.services.knowledge_quality_service.persist_application_snapshot",
        new=AsyncMock(return_value=snapshot),
    ), patch(
        "app.services.knowledge_application_service.write_audit",
        new=AsyncMock(),
    ):
        validated = await knowledge_application_service.validate_release(db, MEMBER, "app-1", "rel-1")

    assert validated.status == ApplicationReleaseStatus.validated.value
    assert validated.quality_snapshot_id == "snap-1"


@pytest.mark.asyncio
async def test_validate_release_fails_on_quality_gate(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    release = _release(status=ApplicationReleaseStatus.draft.value)
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    readiness = SimpleNamespace(ready=True, to_dict=lambda: {"ready": True})
    snapshot = _snapshot(gate_result=QualityGateResult.fail.value)

    with patch(
        "app.services.knowledge_application_service.get_application",
        new=AsyncMock(return_value=_app()),
    ), patch(
        "app.services.knowledge_application_service.has_application_permission",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.knowledge_application_service.get_release",
        new=AsyncMock(return_value=release),
    ), patch(
        "app.services.application_readiness_service.check",
        new=AsyncMock(return_value=readiness),
    ), patch(
        "app.services.knowledge_quality_service.persist_application_snapshot",
        new=AsyncMock(return_value=snapshot),
    ):
        with pytest.raises(ConflictError) as exc:
            await knowledge_application_service.validate_release(db, MEMBER, "app-1", "rel-1")
    assert exc.value.message_key == "errors.knowledge.quality_gate_failed"
    assert release.status == ApplicationReleaseStatus.failed.value


@pytest.mark.asyncio
async def test_promote_stable_requires_pass_gate(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    release = _release(status=ApplicationReleaseStatus.validated.value, snapshot_id="snap-1")
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
    db.get = AsyncMock(return_value=_snapshot(gate_result=QualityGateResult.fail.value))
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with patch(
        "app.services.release_promotion_service.get_application",
        new=AsyncMock(return_value=_app()),
    ), patch(
        "app.services.release_promotion_service.has_application_permission",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.release_promotion_service.get_release",
        new=AsyncMock(return_value=release),
    ), patch(
        "app.services.release_promotion_service._get_channel",
        new=AsyncMock(return_value=channel),
    ):
        with pytest.raises(ConflictError) as exc:
            await release_promotion_service.promote(
                db, MEMBER, "app-1", channel="stable", release_id="rel-1"
            )
    assert exc.value.message_key == "errors.knowledge.quality_gate_failed"


@pytest.mark.asyncio
async def test_promote_stable_updates_channel_pointer(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    release = _release(status=ApplicationReleaseStatus.validated.value, snapshot_id="snap-1")
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
    db.get = AsyncMock(return_value=_snapshot(gate_result=QualityGateResult.pass_.value))
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with patch(
        "app.services.release_promotion_service.get_application",
        new=AsyncMock(return_value=_app()),
    ), patch(
        "app.services.release_promotion_service.has_application_permission",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.release_promotion_service.get_release",
        new=AsyncMock(return_value=release),
    ), patch(
        "app.services.release_promotion_service._get_channel",
        new=AsyncMock(return_value=channel),
    ), patch(
        "app.services.release_promotion_service.write_audit",
        new=AsyncMock(),
    ):
        updated = await release_promotion_service.promote(
            db, MEMBER, "app-1", channel="stable", release_id="rel-1"
        )

    assert updated.active_release_id == "rel-1"
    assert release.status == ApplicationReleaseStatus.promoted.value


@pytest.mark.asyncio
async def test_publish_application_uses_release_flow_when_v24(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    app = _app()
    release = _release(status=ApplicationReleaseStatus.validated.value)
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    readiness = SimpleNamespace(ready=True, to_dict=lambda: {"ready": True})

    with patch(
        "app.services.knowledge_application_service.get_application",
        new=AsyncMock(return_value=app),
    ), patch(
        "app.services.knowledge_application_service.has_application_permission",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.application_readiness_service.check",
        new=AsyncMock(return_value=readiness),
    ), patch(
        "app.services.knowledge_application_service.create_release",
        new=AsyncMock(return_value=release),
    ) as create_release, patch(
        "app.services.knowledge_application_service.validate_release",
        new=AsyncMock(return_value=release),
    ) as validate_release, patch(
        "app.services.release_promotion_service.promote",
        new=AsyncMock(return_value=SimpleNamespace(active_release_id="rel-1")),
    ) as promote, patch(
        "app.services.knowledge_quality_service.build_runtime_snapshot",
        new=AsyncMock(return_value={"published_at": "now"}),
    ):
        published = await knowledge_application_service.publish_application(db, MEMBER, "app-1")

    create_release.assert_awaited_once()
    validate_release.assert_awaited_once()
    promote.assert_awaited_once()
    assert published.status == "active"


@pytest.mark.asyncio
async def test_evaluate_gate_fail_on_binding_issues():
    payload = {
        "score_status": "partial",
        "subscores": {"runtime_binding": 0.0, "index_readiness": 1.0},
        "issues": ["runtime_binding_inactive"],
    }
    gate_result, details = knowledge_quality_service.evaluate_gate(payload)
    assert gate_result == QualityGateResult.fail.value
    assert "runtime_binding_inactive" in details["checks"]["fail_reasons"]


@pytest.mark.asyncio
async def test_quality_history_reads_snapshots(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    row = SimpleNamespace(
        id="snap-1",
        scope_type="knowledge_base",
        scope_id="kb-1",
        manifest_hash=None,
        release_id=None,
        subscores={"runtime_binding": 1.0},
        coverage={},
        issues=[],
        overall_status="complete",
        gate_result=QualityGateResult.pass_.value,
        gate_details={},
        calculated_at=datetime.now(UTC),
    )
    kb = SimpleNamespace(id="kb-1", org_id="org-1", deleted_at=None)
    db = MagicMock()
    db.get = AsyncMock(return_value=kb)
    db.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[row])))

    with patch(
        "app.services.knowledge_application_service.get_application",
        new=AsyncMock(),
    ):
        history = await knowledge_quality_service.get_quality_history(
            db,
            MEMBER,
            scope_type="knowledge_base",
            scope_id="kb-1",
        )

    assert len(history) == 1
    assert history[0]["id"] == "snap-1"
    assert history[0]["gate_result"] == QualityGateResult.pass_.value

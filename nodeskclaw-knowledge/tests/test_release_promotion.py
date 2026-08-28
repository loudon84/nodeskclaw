"""Release promotion lock, ChannelEvent rollback, and eligibility gates."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.core.exceptions import ConflictError
from app.models.enums import ApplicationReleaseStatus, QualityGateResult
from app.schemas.principal import KnowledgePrincipal
from app.services import release_integrity_service, release_promotion_service


MEMBER = KnowledgePrincipal(
    user_id="user-1",
    member_id="member-1",
    org_id="org-1",
    name="Tester",
)


def _app(*, status="draft"):
    return SimpleNamespace(
        id="app-1",
        org_id="org-1",
        owner_member_id="member-1",
        deleted_at=None,
        status=status,
    )


def _release(
    *,
    release_id="rel-new",
    status=ApplicationReleaseStatus.validated.value,
    version=2,
    snapshot_id="snap-1",
    manifest_hash="hash-1",
):
    return SimpleNamespace(
        id=release_id,
        org_id="org-1",
        application_id="app-1",
        version=version,
        status=status,
        release_manifest={"application_id": "app-1", "knowledge_sets": []},
        manifest_hash=manifest_hash,
        quality_snapshot_id=snapshot_id,
        promoted_at=None,
        deleted_at=None,
    )


def _channel(*, active_release_id=None, channel="stable"):
    return SimpleNamespace(
        id="ch-1",
        application_id="app-1",
        channel=channel,
        active_release_id=active_release_id,
        updated_by_member_id=None,
        updated_at=datetime.now(UTC),
        deleted_at=None,
    )


def _snapshot(*, gate_result=QualityGateResult.pass_.value, manifest_hash="hash-1", calculated_at=None):
    return SimpleNamespace(
        id="snap-1",
        deleted_at=None,
        gate_result=gate_result,
        manifest_hash=manifest_hash,
        calculated_at=calculated_at or datetime.now(UTC),
    )


def _event(*, action, from_release_id, to_release_id, created_at=None):
    return SimpleNamespace(
        action=action,
        from_release_id=from_release_id,
        to_release_id=to_release_id,
        deleted_at=None,
        created_at=created_at or datetime.now(UTC),
        id="evt",
    )


def _scalars(events):
    result = MagicMock()
    result.all.return_value = events
    return result


def _integrity(status="healthy", reasons=None):
    return release_integrity_service.ReleaseIntegrityResult(
        status=status,
        reasons=reasons or [],
    )


# @lat: [[knowledge#Knowledge Product Lifecycle V24#Release Promotion Gates#Stable promote writes application active]]
@pytest.mark.asyncio
async def test_stable_promote_sets_application_active_without_superseding(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    previous = _release(
        release_id="rel-prev",
        status=ApplicationReleaseStatus.validated.value,
        version=1,
    )
    release = _release(release_id="rel-new", version=2)
    channel = _channel(active_release_id="rel-prev", channel="stable")
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    async def fake_get(model_cls, obj_id):
        if model_cls.__name__ == "KnowledgeQualitySnapshot":
            return _snapshot()
        if obj_id == "rel-prev":
            return previous
        return None

    db.get = AsyncMock(side_effect=fake_get)
    app = _app()

    with patch(
        "app.services.release_promotion_service.get_application",
        new=AsyncMock(return_value=app),
    ), patch(
        "app.services.release_promotion_service.has_application_permission",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.release_promotion_service.get_release",
        new=AsyncMock(return_value=release),
    ), patch(
        "app.services.release_promotion_service.application_advisory_xact_lock",
        new=AsyncMock(),
    ), patch(
        "app.services.release_promotion_service._get_channel",
        new=AsyncMock(return_value=channel),
    ), patch(
        "app.services.release_integrity_service.evaluate",
        new=AsyncMock(return_value=_integrity()),
    ), patch(
        "app.services.release_promotion_service.write_audit",
        new=AsyncMock(),
    ):
        updated = await release_promotion_service.promote(
            db, MEMBER, "app-1", channel="stable", release_id="rel-new"
        )

    assert updated.active_release_id == "rel-new"
    assert previous.status == ApplicationReleaseStatus.validated.value
    assert release.status == ApplicationReleaseStatus.validated.value
    assert db.add.called
    event = db.add.call_args[0][0]
    assert event.from_release_id == "rel-prev"
    assert event.to_release_id == "rel-new"
    assert event.action == "promote"
    assert app.status == "active"


@pytest.mark.asyncio
async def test_rollback_uses_channel_event_from_release_id(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    target = _release(release_id="rel-prev", version=1)
    channel = _channel(active_release_id="rel-new", channel="stable")
    app = _app(status="active")
    db = MagicMock()
    db.scalars = AsyncMock(
        return_value=_scalars(
            [
                _event(action="promote", from_release_id=None, to_release_id="rel-prev"),
                _event(action="promote", from_release_id="rel-prev", to_release_id="rel-new"),
            ]
        )
    )

    async def fake_get(model_cls, obj_id):
        if model_cls.__name__ == "KnowledgeQualitySnapshot":
            return _snapshot()
        if obj_id == "rel-prev":
            return target
        return None

    db.get = AsyncMock(side_effect=fake_get)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with patch(
        "app.services.release_promotion_service.get_application",
        new=AsyncMock(return_value=app),
    ), patch(
        "app.services.release_promotion_service.has_application_permission",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.release_promotion_service.application_advisory_xact_lock",
        new=AsyncMock(),
    ), patch(
        "app.services.release_promotion_service._get_channel",
        new=AsyncMock(return_value=channel),
    ), patch(
        "app.services.release_integrity_service.evaluate",
        new=AsyncMock(return_value=_integrity()),
    ), patch(
        "app.services.release_promotion_service.write_audit",
        new=AsyncMock(),
    ):
        updated = await release_promotion_service.rollback(db, MEMBER, "app-1", channel="stable")

    assert updated.active_release_id == "rel-prev"
    assert target.status == ApplicationReleaseStatus.validated.value
    assert app.status == "active"
    event = db.add.call_args[0][0]
    assert event.from_release_id == "rel-new"
    assert event.to_release_id == "rel-prev"
    assert event.action == "rollback"


@pytest.mark.asyncio
async def test_rollback_rejects_when_no_history(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    channel = _channel(active_release_id="rel-new", channel="stable")
    db = MagicMock()
    db.scalars = AsyncMock(
        return_value=_scalars(
            [_event(action="promote", from_release_id=None, to_release_id="rel-new")]
        )
    )

    with patch(
        "app.services.release_promotion_service.get_application",
        new=AsyncMock(return_value=_app()),
    ), patch(
        "app.services.release_promotion_service.has_application_permission",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.release_promotion_service.application_advisory_xact_lock",
        new=AsyncMock(),
    ), patch(
        "app.services.release_promotion_service._get_channel",
        new=AsyncMock(return_value=channel),
    ):
        with pytest.raises(ConflictError) as exc:
            await release_promotion_service.rollback(db, MEMBER, "app-1", channel="stable")

    assert exc.value.message_key == "errors.knowledge.release_rollback_unavailable"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("integrity_status", "reasons"),
    [
        ("stale", ["index_version_drift:kb-1:chunk"]),
        ("unavailable", ["manifest_hash_mismatch"]),
    ],
)
async def test_stable_promote_refuses_integrity_stale_or_unavailable(
    monkeypatch,
    integrity_status,
    reasons,
):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    release = _release()
    channel = _channel(channel="stable")
    db = MagicMock()
    db.get = AsyncMock(return_value=_snapshot())

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
        "app.services.release_promotion_service.application_advisory_xact_lock",
        new=AsyncMock(),
    ), patch(
        "app.services.release_promotion_service._get_channel",
        new=AsyncMock(return_value=channel),
    ), patch(
        "app.services.release_integrity_service.evaluate",
        new=AsyncMock(return_value=_integrity(status=integrity_status, reasons=reasons)),
    ):
        with pytest.raises(ConflictError) as exc:
            await release_promotion_service.promote(
                db, MEMBER, "app-1", channel="stable", release_id="rel-new"
            )

    assert exc.value.message_key == "errors.knowledge.release_integrity_unhealthy"


@pytest.mark.asyncio
async def test_preview_promote_allows_validated_without_pass_quality(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    release = _release(snapshot_id=None)
    channel = _channel(channel="preview")
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    app = _app()

    with patch(
        "app.services.release_promotion_service.get_application",
        new=AsyncMock(return_value=app),
    ), patch(
        "app.services.release_promotion_service.has_application_permission",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.release_promotion_service.get_release",
        new=AsyncMock(return_value=release),
    ), patch(
        "app.services.release_promotion_service.application_advisory_xact_lock",
        new=AsyncMock(),
    ), patch(
        "app.services.release_promotion_service._get_channel",
        new=AsyncMock(return_value=channel),
    ), patch(
        "app.services.release_integrity_service.evaluate",
        new=AsyncMock(return_value=_integrity(status="stale", reasons=["index_version_drift:kb-1:chunk"])),
    ), patch(
        "app.services.release_promotion_service.write_audit",
        new=AsyncMock(),
    ):
        updated = await release_promotion_service.promote(
            db, MEMBER, "app-1", channel="preview", release_id="rel-new"
        )

    assert updated.active_release_id == "rel-new"
    assert release.status == ApplicationReleaseStatus.validated.value
    assert app.status == "draft"


# @lat: [[knowledge#Knowledge Product Lifecycle V24#Release Promotion Gates#Stable refuse stale quality snapshot]]
@pytest.mark.asyncio
async def test_stable_promote_refuses_stale_quality_snapshot(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    monkeypatch.setattr(settings, "KNOWLEDGE_RELEASE_QUALITY_MAX_AGE_SECONDS", 900)
    release = _release()
    channel = _channel(channel="stable")
    db = MagicMock()
    stale_at = datetime.now(UTC).replace(year=2020)
    db.get = AsyncMock(return_value=_snapshot(calculated_at=stale_at))

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
        "app.services.release_promotion_service.application_advisory_xact_lock",
        new=AsyncMock(),
    ), patch(
        "app.services.release_promotion_service._get_channel",
        new=AsyncMock(return_value=channel),
    ), patch(
        "app.services.release_integrity_service.evaluate",
        new=AsyncMock(return_value=_integrity()),
    ):
        with pytest.raises(ConflictError) as exc:
            await release_promotion_service.promote(
                db, MEMBER, "app-1", channel="stable", release_id="rel-new"
            )

    assert exc.value.message_key == "errors.knowledge.release_quality_snapshot_stale"


# @lat: [[knowledge#Knowledge Product Lifecycle V24#Release Promotion Gates#Preview skips freshness gate]]
@pytest.mark.asyncio
async def test_preview_promote_skips_freshness_gate(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    monkeypatch.setattr(settings, "KNOWLEDGE_RELEASE_QUALITY_MAX_AGE_SECONDS", 1)
    release = _release()
    channel = _channel(channel="preview")
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.get = AsyncMock(return_value=_snapshot(calculated_at=datetime.now(UTC).replace(year=2020)))
    app = _app()

    with patch(
        "app.services.release_promotion_service.get_application",
        new=AsyncMock(return_value=app),
    ), patch(
        "app.services.release_promotion_service.has_application_permission",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.release_promotion_service.get_release",
        new=AsyncMock(return_value=release),
    ), patch(
        "app.services.release_promotion_service.application_advisory_xact_lock",
        new=AsyncMock(),
    ), patch(
        "app.services.release_promotion_service._get_channel",
        new=AsyncMock(return_value=channel),
    ), patch(
        "app.services.release_integrity_service.evaluate",
        new=AsyncMock(return_value=_integrity()),
    ), patch(
        "app.services.release_promotion_service.write_audit",
        new=AsyncMock(),
    ):
        updated = await release_promotion_service.promote(
            db, MEMBER, "app-1", channel="preview", release_id="rel-new"
        )

    assert updated.active_release_id == "rel-new"
    assert app.status == "draft"


# @lat: [[knowledge#Knowledge Product Lifecycle V24#Release Promotion Gates#Rollback is history-back not toggle]]
@pytest.mark.asyncio
async def test_rollback_history_back_second_step_is_r1_not_toggle(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    target = _release(release_id="rel-r1", version=1)
    channel = _channel(active_release_id="rel-r2", channel="stable")
    db = MagicMock()
    db.scalars = AsyncMock(
        return_value=_scalars(
            [
                _event(action="promote", from_release_id=None, to_release_id="rel-r1"),
                _event(action="promote", from_release_id="rel-r1", to_release_id="rel-r2"),
                _event(action="promote", from_release_id="rel-r2", to_release_id="rel-r3"),
                _event(action="rollback", from_release_id="rel-r3", to_release_id="rel-r2"),
            ]
        )
    )

    async def fake_get(model_cls, obj_id):
        if model_cls.__name__ == "KnowledgeQualitySnapshot":
            return _snapshot()
        if obj_id == "rel-r1":
            return target
        return None

    db.get = AsyncMock(side_effect=fake_get)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with patch(
        "app.services.release_promotion_service.get_application",
        new=AsyncMock(return_value=_app(status="active")),
    ), patch(
        "app.services.release_promotion_service.has_application_permission",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.release_promotion_service.application_advisory_xact_lock",
        new=AsyncMock(),
    ), patch(
        "app.services.release_promotion_service._get_channel",
        new=AsyncMock(return_value=channel),
    ), patch(
        "app.services.release_integrity_service.evaluate",
        new=AsyncMock(return_value=_integrity()),
    ), patch(
        "app.services.release_promotion_service.write_audit",
        new=AsyncMock(),
    ):
        updated = await release_promotion_service.rollback(db, MEMBER, "app-1", channel="stable")

    assert updated.active_release_id == "rel-r1"
    event = db.add.call_args[0][0]
    assert event.to_release_id == "rel-r1"
    assert event.from_release_id == "rel-r2"


@pytest.mark.asyncio
async def test_rollback_branch_after_r4_returns_to_r2(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    target = _release(release_id="rel-r2", version=2)
    channel = _channel(active_release_id="rel-r4", channel="stable")
    db = MagicMock()
    db.scalars = AsyncMock(
        return_value=_scalars(
            [
                _event(action="promote", from_release_id=None, to_release_id="rel-r1"),
                _event(action="promote", from_release_id="rel-r1", to_release_id="rel-r2"),
                _event(action="promote", from_release_id="rel-r2", to_release_id="rel-r3"),
                _event(action="rollback", from_release_id="rel-r3", to_release_id="rel-r2"),
                _event(action="promote", from_release_id="rel-r2", to_release_id="rel-r4"),
            ]
        )
    )

    async def fake_get(model_cls, obj_id):
        if model_cls.__name__ == "KnowledgeQualitySnapshot":
            return _snapshot()
        if obj_id == "rel-r2":
            return target
        return None

    db.get = AsyncMock(side_effect=fake_get)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with patch(
        "app.services.release_promotion_service.get_application",
        new=AsyncMock(return_value=_app(status="active")),
    ), patch(
        "app.services.release_promotion_service.has_application_permission",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.release_promotion_service.application_advisory_xact_lock",
        new=AsyncMock(),
    ), patch(
        "app.services.release_promotion_service._get_channel",
        new=AsyncMock(return_value=channel),
    ), patch(
        "app.services.release_integrity_service.evaluate",
        new=AsyncMock(return_value=_integrity()),
    ), patch(
        "app.services.release_promotion_service.write_audit",
        new=AsyncMock(),
    ):
        updated = await release_promotion_service.rollback(db, MEMBER, "app-1", channel="stable")

    assert updated.active_release_id == "rel-r2"


# @lat: [[knowledge#Knowledge Product Lifecycle V24#Release Promotion Gates#Stale previous blocks without skipping]]
@pytest.mark.asyncio
async def test_rollback_stale_previous_blocks_without_skipping(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    monkeypatch.setattr(settings, "KNOWLEDGE_RELEASE_QUALITY_MAX_AGE_SECONDS", 900)
    target = _release(release_id="rel-prev", version=1)
    channel = _channel(active_release_id="rel-new", channel="stable")
    db = MagicMock()
    db.scalars = AsyncMock(
        return_value=_scalars(
            [
                _event(action="promote", from_release_id=None, to_release_id="rel-prev"),
                _event(action="promote", from_release_id="rel-prev", to_release_id="rel-new"),
            ]
        )
    )

    async def fake_get(model_cls, obj_id):
        if model_cls.__name__ == "KnowledgeQualitySnapshot":
            return _snapshot(calculated_at=datetime.now(UTC).replace(year=2020))
        if obj_id == "rel-prev":
            return target
        return None

    db.get = AsyncMock(side_effect=fake_get)

    with patch(
        "app.services.release_promotion_service.get_application",
        new=AsyncMock(return_value=_app(status="active")),
    ), patch(
        "app.services.release_promotion_service.has_application_permission",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.release_promotion_service.application_advisory_xact_lock",
        new=AsyncMock(),
    ), patch(
        "app.services.release_promotion_service._get_channel",
        new=AsyncMock(return_value=channel),
    ), patch(
        "app.services.release_integrity_service.evaluate",
        new=AsyncMock(return_value=_integrity()),
    ):
        with pytest.raises(ConflictError) as exc:
            await release_promotion_service.rollback(db, MEMBER, "app-1", channel="stable")

    assert exc.value.message_key == "errors.knowledge.release_quality_snapshot_stale"
    assert channel.active_release_id == "rel-new"

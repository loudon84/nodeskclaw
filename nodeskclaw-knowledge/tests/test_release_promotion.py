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


def _app():
    return SimpleNamespace(
        id="app-1",
        org_id="org-1",
        owner_member_id="member-1",
        deleted_at=None,
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


def _snapshot(*, gate_result=QualityGateResult.pass_.value, manifest_hash="hash-1"):
    return SimpleNamespace(
        id="snap-1",
        deleted_at=None,
        gate_result=gate_result,
        manifest_hash=manifest_hash,
    )


def _integrity(status="healthy", reasons=None):
    return release_integrity_service.ReleaseIntegrityResult(
        status=status,
        reasons=reasons or [],
    )


@pytest.mark.asyncio
async def test_promote_does_not_supersede_previous_release_still_referenced(monkeypatch):
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


@pytest.mark.asyncio
async def test_rollback_uses_channel_event_from_release_id(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    target = _release(release_id="rel-prev", version=1)
    channel = _channel(active_release_id="rel-new", channel="stable")
    latest_event = SimpleNamespace(
        from_release_id="rel-prev",
        to_release_id="rel-new",
        deleted_at=None,
        created_at=datetime.now(UTC),
    )
    db = MagicMock()

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
    ), patch(
        "app.services.release_promotion_service._get_latest_channel_event",
        new=AsyncMock(return_value=latest_event),
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
    event = db.add.call_args[0][0]
    assert event.from_release_id == "rel-new"
    assert event.to_release_id == "rel-prev"
    assert event.action == "rollback"


@pytest.mark.asyncio
async def test_rollback_rejects_when_no_history(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    channel = _channel(active_release_id="rel-new", channel="stable")
    db = MagicMock()

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
    ), patch(
        "app.services.release_promotion_service._get_latest_channel_event",
        new=AsyncMock(return_value=None),
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

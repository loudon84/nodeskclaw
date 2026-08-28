"""Tests for release_runtime_service — ReleaseExecutionContext resolution."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.models.enums import ApplicationReleaseStatus
from app.schemas.principal import KnowledgePrincipal
from app.services import application_retrieval_policy_service, release_integrity_service, release_manifest_service
from app.services.release_runtime_service import resolve_application_release


MEMBER = KnowledgePrincipal(
    user_id="user-1",
    member_id="member-1",
    org_id="org-1",
    name="Tester",
)


def _manifest():
    return {
        "schema_version": 1,
        "application_id": "app-1",
        "release_version": 1,
        "retrieval_policy_revision_id": "policy-1",
        "answer_model": "gpt-4",
        "knowledge_sets": [
            {
                "knowledge_set_id": "set-1",
                "knowledge_bases": [
                    {"knowledge_base_id": "kb-1", "weight": 1.5},
                ],
            }
        ],
    }


def _channel_row(*, active_release_id="rel-1"):
    return SimpleNamespace(
        application_id="app-1",
        channel="stable",
        active_release_id=active_release_id,
        deleted_at=None,
    )


def _release(*, status=ApplicationReleaseStatus.validated.value, manifest=None, manifest_hash=None):
    manifest = manifest or _manifest()
    stored_hash = manifest_hash
    if stored_hash is None:
        stored_hash = release_manifest_service.manifest_hash(manifest)
    return SimpleNamespace(
        id="rel-1",
        org_id="org-1",
        application_id="app-1",
        version=1,
        status=status,
        release_manifest=manifest,
        manifest_hash=stored_hash,
        deleted_at=None,
    )


def _policy_revision():
    return SimpleNamespace(
        id="policy-1",
        application_id="app-1",
        org_id="org-1",
        deleted_at=None,
        status="active",
        query_intelligence_policy={"term_expansion": True},
        provider_policy={"allow_chunk": True, "allow_question": False},
        provider_weights={"chunk": 2.0, "question": 0.25},
        candidate_budget={"max_candidates": 512},
        fanout_budget={"max_kb_fanout": 4},
        latency_budget={"max_ms": 15000},
        fallback_policy={"mode": "semantic_only"},
        artifact_policy={"allow_outline": False, "allow_table": True, "max_artifacts": 32},
        fusion_policy={"mode": "rrf", "k": 40},
    )


def _db(*, release, policy_revision=None):
    db = MagicMock()
    db.scalar = AsyncMock(return_value=_channel_row())
    db.get = AsyncMock(
        side_effect=lambda model, obj_id: {
            release.id: release,
            "policy-1": policy_revision or _policy_revision(),
        }.get(obj_id)
    )
    return db


# @lat: [[knowledge#Product Delivery V24#Release Runtime Resolution#Same channel stable identity]]
@pytest.mark.asyncio
async def test_same_channel_resolves_same_release_id_and_hash(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    release = _release()
    db = _db(release=release)

    with patch(
        "app.services.release_integrity_service.evaluate",
        new=AsyncMock(
            return_value=release_integrity_service.ReleaseIntegrityResult(status="healthy", reasons=[])
        ),
    ):
        implicit = await resolve_application_release(db, MEMBER, application_id="app-1", channel="stable")
        explicit = await resolve_application_release(
            db,
            MEMBER,
            application_id="app-1",
            channel="stable",
            release_id="rel-1",
        )

    assert implicit.release_id == explicit.release_id == "rel-1"
    assert implicit.manifest_hash == explicit.manifest_hash
    assert implicit.manifest_hash == release.manifest_hash


# @lat: [[knowledge#Product Delivery V24#Release Runtime Resolution#Promoted release rejected]]
@pytest.mark.asyncio
async def test_promoted_status_fails(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    release = _release(status=ApplicationReleaseStatus.promoted.value)
    db = _db(release=release)

    with pytest.raises(BadRequestError) as exc:
        await resolve_application_release(db, MEMBER, application_id="app-1", channel="stable")

    assert exc.value.message_key == "errors.knowledge.release_not_validated"


# @lat: [[knowledge#Product Delivery V24#Release Runtime Resolution#Manifest hash mismatch]]
@pytest.mark.asyncio
async def test_hash_mismatch_fails(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    manifest = _manifest()
    release = _release(manifest=manifest, manifest_hash="deadbeef")
    db = _db(release=release)

    with pytest.raises(BadRequestError) as exc:
        await resolve_application_release(db, MEMBER, application_id="app-1", channel="stable")

    assert exc.value.message_key == "errors.knowledge.release_manifest_hash_mismatch"


# @lat: [[knowledge#Product Delivery V24#Release Runtime Resolution#Integrity stale]]
@pytest.mark.asyncio
async def test_integrity_stale_fails(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    release = _release()
    db = _db(release=release)

    with patch(
        "app.services.release_integrity_service.evaluate",
        new=AsyncMock(
            return_value=release_integrity_service.ReleaseIntegrityResult(
                status="stale",
                reasons=["input_manifest_hash_drift:kb-1"],
            )
        ),
    ):
        with pytest.raises(BadRequestError) as exc:
            await resolve_application_release(db, MEMBER, application_id="app-1", channel="stable")

    assert exc.value.message_key == "errors.knowledge.release_integrity_unhealthy"


# @lat: [[knowledge#Product Delivery V24#Release Runtime Resolution#Success includes compiled policy]]
@pytest.mark.asyncio
async def test_success_includes_compiled_policy(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    release = _release()
    policy_revision = _policy_revision()
    db = _db(release=release, policy_revision=policy_revision)
    expected_policy = application_retrieval_policy_service.compile_execution_policy(policy_revision)

    with patch(
        "app.services.release_integrity_service.evaluate",
        new=AsyncMock(
            return_value=release_integrity_service.ReleaseIntegrityResult(status="healthy", reasons=[])
        ),
    ):
        context = await resolve_application_release(db, MEMBER, application_id="app-1", channel="stable")

    assert context.compiled_policy == expected_policy
    assert context.application_id == "app-1"
    assert context.answer_model == "gpt-4"
    assert context.knowledge_set_ids == ["set-1"]
    assert context.knowledge_bases == [
        {"knowledge_base_id": "kb-1", "weight": 1.5, "knowledge_set_id": "set-1"}
    ]
    assert context.retrieval_policy_revision_id == "policy-1"
    assert context.integrity_status == "healthy"
    assert context.manifest_hash == release.manifest_hash

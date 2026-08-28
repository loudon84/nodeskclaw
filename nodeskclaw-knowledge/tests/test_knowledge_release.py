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
    application_retrieval_policy_service,
    knowledge_application_service,
    knowledge_quality_service,
    release_integrity_service,
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


def _release(*, status="draft", version=1, manifest=None, snapshot_id=None, validation_job_id=None, manifest_hash=None):
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
        manifest_hash=manifest_hash,
        quality_snapshot_id=snapshot_id,
        validation_job_id=validation_job_id,
        validation_error=None,
        created_by_member_id="member-1",
        promoted_at=None,
        retired_at=None,
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


def _snapshot(*, gate_result=QualityGateResult.pass_.value, manifest_hash="hash-1"):
    return SimpleNamespace(
        id="snap-1",
        deleted_at=None,
        gate_result=gate_result,
        manifest_hash=manifest_hash,
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
        "app.services.advisory_lock.application_advisory_xact_lock",
        new=AsyncMock(),
    ), patch(
        "app.services.release_manifest_service.build",
        new=AsyncMock(
            return_value={
                "schema_version": 1,
                "application_id": "app-1",
                "release_version": 3,
                "retrieval_policy_revision_id": "policy-1",
                "answer_model": "gpt-4",
                "knowledge_sets": [],
            }
        ),
    ), patch(
        "app.services.release_manifest_service.manifest_hash",
        return_value="manifest-hash-3",
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
    assert release.manifest_hash == "manifest-hash-3"


@pytest.mark.asyncio
async def test_validate_release_enqueues_job_and_sets_validating(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    release = _release(status=ApplicationReleaseStatus.draft.value)
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    job = SimpleNamespace(id="job-1", target_key="validate_only")

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
        "app.services.build_orchestrator.enqueue_build",
        new=AsyncMock(return_value=job),
    ) as enqueue_build, patch(
        "app.services.knowledge_quality_service.persist_application_snapshot",
        new=AsyncMock(),
    ) as persist_snapshot, patch(
        "app.services.knowledge_application_service.write_audit",
        new=AsyncMock(),
    ):
        validated = await knowledge_application_service.validate_release(db, MEMBER, "app-1", "rel-1")

    assert validated.status == ApplicationReleaseStatus.validating.value
    assert validated.validation_job_id == "job-1"
    enqueue_build.assert_awaited_once()
    persist_snapshot.assert_not_called()
    kwargs = enqueue_build.await_args.kwargs
    assert kwargs["target_kind"] == "release_validation"
    assert kwargs["target_key"] == "validate_only"
    assert kwargs["release_candidate_id"] == "rel-1"


@pytest.mark.asyncio
async def test_validate_release_promote_on_validated_uses_promote_stable_target(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    release = _release(status=ApplicationReleaseStatus.draft.value)
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    job = SimpleNamespace(id="job-2", target_key="validate_only")

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
        "app.services.build_orchestrator.enqueue_build",
        new=AsyncMock(return_value=job),
    ) as enqueue_build, patch(
        "app.services.knowledge_application_service.write_audit",
        new=AsyncMock(),
    ):
        validated = await knowledge_application_service.validate_release(
            db,
            MEMBER,
            "app-1",
            "rel-1",
            promote_on_validated=True,
        )

    assert validated.status == ApplicationReleaseStatus.validating.value
    assert job.target_key == "promote_stable"
    assert enqueue_build.await_args.kwargs["target_key"] == "promote_stable"


@pytest.mark.asyncio
async def test_promote_stable_requires_pass_gate(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    release = _release(
        status=ApplicationReleaseStatus.validated.value,
        snapshot_id="snap-1",
        manifest_hash="hash-1",
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
        "app.services.release_promotion_service.application_advisory_xact_lock",
        new=AsyncMock(),
    ), patch(
        "app.services.release_promotion_service._get_channel",
        new=AsyncMock(return_value=channel),
    ), patch(
        "app.services.release_integrity_service.evaluate",
        new=AsyncMock(
            return_value=release_integrity_service.ReleaseIntegrityResult(status="healthy", reasons=[])
        ),
    ):
        with pytest.raises(ConflictError) as exc:
            await release_promotion_service.promote(
                db, MEMBER, "app-1", channel="stable", release_id="rel-1"
            )
    assert exc.value.message_key == "errors.knowledge.quality_gate_failed"


@pytest.mark.asyncio
async def test_promote_stable_updates_channel_pointer(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    release = _release(
        status=ApplicationReleaseStatus.validated.value,
        snapshot_id="snap-1",
        manifest_hash="hash-1",
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
        "app.services.release_promotion_service.application_advisory_xact_lock",
        new=AsyncMock(),
    ), patch(
        "app.services.release_promotion_service._get_channel",
        new=AsyncMock(return_value=channel),
    ), patch(
        "app.services.release_integrity_service.evaluate",
        new=AsyncMock(
            return_value=release_integrity_service.ReleaseIntegrityResult(status="healthy", reasons=[])
        ),
    ), patch(
        "app.services.release_promotion_service.write_audit",
        new=AsyncMock(),
    ):
        updated = await release_promotion_service.promote(
            db, MEMBER, "app-1", channel="stable", release_id="rel-1"
        )

    assert updated.active_release_id == "rel-1"
    assert release.status == ApplicationReleaseStatus.validated.value


@pytest.mark.asyncio
async def test_publish_application_uses_release_flow_when_v24(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    app = _app()
    release = _release(status=ApplicationReleaseStatus.validating.value, validation_job_id="job-1")
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with patch(
        "app.services.knowledge_application_service.get_application",
        new=AsyncMock(return_value=app),
    ), patch(
        "app.services.knowledge_application_service.has_application_permission",
        new=AsyncMock(return_value=True),
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
    validate_release.assert_awaited_once_with(
        db,
        MEMBER,
        "app-1",
        "rel-1",
        promote_on_validated=False,
    )
    promote.assert_not_called()
    assert published.status == "active"
    assert published.validation_job_id == "job-1"


@pytest.mark.asyncio
async def test_publish_application_promote_on_validated_passes_flag(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V24_RELEASE_ENABLED", True)
    app = _app()
    release = _release(status=ApplicationReleaseStatus.validating.value, validation_job_id="job-2")
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with patch(
        "app.services.knowledge_application_service.get_application",
        new=AsyncMock(return_value=app),
    ), patch(
        "app.services.knowledge_application_service.has_application_permission",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.services.knowledge_application_service.create_release",
        new=AsyncMock(return_value=release),
    ), patch(
        "app.services.knowledge_application_service.validate_release",
        new=AsyncMock(return_value=release),
    ) as validate_release, patch(
        "app.services.knowledge_quality_service.build_runtime_snapshot",
        new=AsyncMock(return_value={"published_at": "now"}),
    ):
        await knowledge_application_service.publish_application(
            db,
            MEMBER,
            "app-1",
            promote_on_validated=True,
        )

    validate_release.assert_awaited_once_with(
        db,
        MEMBER,
        "app-1",
        "rel-1",
        promote_on_validated=True,
    )


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


def test_compile_execution_policy_raises_when_revision_missing():
    with pytest.raises(BadRequestError) as exc:
        application_retrieval_policy_service.compile_execution_policy(None)
    assert exc.value.message_key == "errors.knowledge.retrieval_policy_revision_required"


def test_compile_execution_policy_flattens_revision_fields():
    revision = SimpleNamespace(
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
    policy = application_retrieval_policy_service.compile_execution_policy(revision)
    assert policy["query_intelligence_policy"] == {"term_expansion": True}
    assert policy["candidate_budget"] == 512
    assert policy["artifact_budget"] == 32
    assert policy["allow_outline_artifact"] is False
    assert policy["allow_table_artifact"] is True
    assert policy["allow_question_enrichment"] is False

"""Application readiness and publish gate tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.core.exceptions import BadRequestError, ConflictError
from app.models.enums import ApplicationStatus
from app.schemas.knowledge import KnowledgeApplicationUpdate
from app.schemas.principal import KnowledgePrincipal
from app.services import application_readiness_service, knowledge_application_service


def _member() -> KnowledgePrincipal:
    return KnowledgePrincipal(
        user_id="u1",
        member_id="m1",
        org_id="o1",
        member_role="member",
    )


@pytest.mark.asyncio
async def test_publish_application_returns_409_when_not_ready(monkeypatch):
    monkeypatch.setattr(
        "app.services.knowledge_application_service.has_application_permission",
        AsyncMock(return_value=True),
    )
    app = SimpleNamespace(
        id="app1",
        org_id="o1",
        status=ApplicationStatus.draft.value,
        active_profile_id=None,
        acl_version=1,
        runtime_snapshot=None,
    )
    db = AsyncMock()
    with (
        patch(
            "app.services.knowledge_application_service.get_application",
            new=AsyncMock(return_value=app),
        ),
        patch(
            "app.services.application_readiness_service.check",
            new=AsyncMock(
                return_value=application_readiness_service.ReadinessResult(
                    ready=False,
                    blocking=[
                        application_readiness_service.ReadinessIssue(
                            code="runtime_chunk_unavailable",
                            knowledge_base_id="kb1",
                        )
                    ],
                )
            ),
        ),
    ):
        with pytest.raises(ConflictError) as exc:
            await knowledge_application_service.publish_application(db, _member(), "app1")
    assert exc.value.message_key == "errors.knowledge.application_not_ready"
    assert exc.value.details["ready"] is False
    assert exc.value.details["blocking"][0]["code"] == "runtime_chunk_unavailable"


def test_patch_schema_rejects_status_field():
    with pytest.raises(ValidationError):
        KnowledgeApplicationUpdate.model_validate({"status": "active"})


@pytest.mark.asyncio
async def test_publish_application_sets_active_when_ready(monkeypatch):
    monkeypatch.setattr(
        "app.services.knowledge_application_service.has_application_permission",
        AsyncMock(return_value=True),
    )
    app = SimpleNamespace(
        id="app1",
        org_id="o1",
        status=ApplicationStatus.draft.value,
        active_profile_id=None,
        acl_version=1,
        runtime_snapshot=None,
    )
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with (
        patch(
            "app.services.knowledge_application_service.get_application",
            new=AsyncMock(return_value=app),
        ),
        patch(
            "app.services.application_readiness_service.check",
            new=AsyncMock(
                return_value=application_readiness_service.ReadinessResult(ready=True)
            ),
        ),
        patch(
            "app.services.knowledge_quality_service.build_runtime_snapshot",
            new=AsyncMock(return_value={"bound_set_ids": [], "knowledge_bases": []}),
        ),
    ):
        result = await knowledge_application_service.publish_application(db, _member(), "app1")

    assert result.status == ApplicationStatus.active.value
    assert result.runtime_snapshot == {"bound_set_ids": [], "knowledge_bases": []}
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_disable_application_active_to_disabled(monkeypatch):
    monkeypatch.setattr(
        "app.services.knowledge_application_service.has_application_permission",
        AsyncMock(return_value=True),
    )
    app = SimpleNamespace(
        id="app1",
        org_id="o1",
        status=ApplicationStatus.active.value,
    )
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with patch(
        "app.services.knowledge_application_service.get_application",
        new=AsyncMock(return_value=app),
    ):
        result = await knowledge_application_service.disable_application(db, _member(), "app1")

    assert result.status == ApplicationStatus.disabled.value
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_disable_application_rejects_non_active(monkeypatch):
    monkeypatch.setattr(
        "app.services.knowledge_application_service.has_application_permission",
        AsyncMock(return_value=True),
    )
    app = SimpleNamespace(
        id="app1",
        org_id="o1",
        status=ApplicationStatus.draft.value,
        active_profile_id=None,
        acl_version=1,
        runtime_snapshot=None,
    )
    db = AsyncMock()
    with patch(
        "app.services.knowledge_application_service.get_application",
        new=AsyncMock(return_value=app),
    ):
        with pytest.raises(BadRequestError) as exc:
            await knowledge_application_service.disable_application(db, _member(), "app1")
    assert exc.value.message_key == "errors.knowledge.application_not_active"


@pytest.mark.asyncio
async def test_disabled_application_can_publish_again(monkeypatch):
    monkeypatch.setattr(
        "app.services.knowledge_application_service.has_application_permission",
        AsyncMock(return_value=True),
    )
    app = SimpleNamespace(
        id="app1",
        org_id="o1",
        status=ApplicationStatus.disabled.value,
    )
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with (
        patch(
            "app.services.knowledge_application_service.get_application",
            new=AsyncMock(return_value=app),
        ),
        patch(
            "app.services.application_readiness_service.check",
            new=AsyncMock(
                return_value=application_readiness_service.ReadinessResult(ready=True)
            ),
        ),
        patch(
            "app.services.knowledge_quality_service.build_runtime_snapshot",
            new=AsyncMock(return_value={"bound_set_ids": [], "knowledge_bases": []}),
        ),
    ):
        result = await knowledge_application_service.publish_application(db, _member(), "app1")

    assert result.status == ApplicationStatus.active.value
    assert result.runtime_snapshot == {"bound_set_ids": [], "knowledge_bases": []}


def test_build_execution_slices_shape():
    from app.services.retrieval_trace_service import build_execution_slices

    item = SimpleNamespace(
        knowledge_base_id="kb1",
        dataset_id="ds1",
        status="success",
        latency_ms=12,
        candidate_count=3,
        safe_count=2,
        runtime_mode="semantic",
        access_scope="full",
        fallback_used=False,
        fallback_reason=None,
        error_code=None,
    )
    rows = build_execution_slices([item])
    assert rows[0]["knowledge_base_id"] == "kb1"
    assert rows[0]["runtime_mode"] == "semantic"
    assert rows[0]["params_safe_view"]["dataset_id"] == "ds1"

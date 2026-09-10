from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.api.v2 import engineering
from app.core.config import settings
from app.core.exceptions import ForbiddenError
from app.models.build_job import KnowledgeBuildJob
from app.models.knowledge_application_release import KnowledgeApplicationRelease
from app.schemas.principal import KnowledgePrincipal


def _member(**kwargs) -> KnowledgePrincipal:
    base = dict(
        user_id="u1",
        member_id="m1",
        org_id="o1",
        member_role="member",
        is_super_admin=False,
    )
    base.update(kwargs)
    return KnowledgePrincipal(**base)


def _job(**kwargs):
    defaults = dict(
        id="bj1",
        org_id="o1",
        knowledge_base_id=None,
        build_profile_id=None,
        index_type="release_validation",
        target_kind="release_validation",
        scope_type=None,
        scope_id=None,
        trigger_reason="validate",
        status="queued",
        progress=0,
        error_code=None,
        error_message=None,
        attempt_count=0,
        finished_at=None,
        created_at=datetime.now(UTC),
        deleted_at=None,
        release_candidate_id="rc1",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _release(**kwargs):
    defaults = dict(
        id="rc1",
        org_id="o1",
        application_id="app1",
        deleted_at=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


@pytest.mark.asyncio
async def test_get_build_release_validation_allows_application_read(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_API_V2_ENABLED", True)
    monkeypatch.setattr(settings, "KNOWLEDGE_V2_BUILD_ENABLED", True)
    job = _job()
    release = _release()
    member = _member()
    db = AsyncMock()

    async def _get(model, oid):
        if model is KnowledgeBuildJob:
            return job
        if model is KnowledgeApplicationRelease:
            return release
        return None

    db.get = AsyncMock(side_effect=_get)

    with (
        patch(
            "app.api.v2.engineering.permission_service.has_kb_permission",
            new=AsyncMock(return_value=False),
        ) as kb_perm,
        patch(
            "app.api.v2.engineering.permission_service.has_application_permission",
            new=AsyncMock(return_value=True),
        ) as app_perm,
    ):
        result = await engineering.get_build("bj1", member, db)

    assert result.data["id"] == "bj1"
    assert result.data["status"] == "queued"
    app_perm.assert_awaited_once()
    kb_perm.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_build_uses_persisted_application_scope(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_API_V2_ENABLED", True)
    monkeypatch.setattr(settings, "KNOWLEDGE_V2_BUILD_ENABLED", True)
    job = _job(
        index_type=None,
        scope_type="application",
        scope_id="app1",
        release_candidate_id=None,
    )
    member = _member()
    db = AsyncMock()
    db.get = AsyncMock(return_value=job)
    with (
        patch(
            "app.api.v2.engineering.permission_service.has_kb_permission",
            new=AsyncMock(return_value=False),
        ) as kb_perm,
        patch(
            "app.api.v2.engineering.permission_service.has_application_permission",
            new=AsyncMock(return_value=True),
        ) as app_perm,
    ):
        result = await engineering.get_build("bj1", member, db)
    assert result.data["id"] == "bj1"
    app_perm.assert_awaited_once()
    kb_perm.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_build_kb_scoped_job_still_requires_kb_read(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_API_V2_ENABLED", True)
    monkeypatch.setattr(settings, "KNOWLEDGE_V2_BUILD_ENABLED", True)
    job = _job(
        knowledge_base_id="kb1",
        index_type="graph",
        target_kind=None,
        release_candidate_id=None,
    )
    member = _member()
    db = AsyncMock()
    db.get = AsyncMock(return_value=job)

    with (
        patch(
            "app.api.v2.engineering.permission_service.has_kb_permission",
            new=AsyncMock(return_value=True),
        ) as kb_perm,
        patch(
            "app.api.v2.engineering.permission_service.has_application_permission",
            new=AsyncMock(return_value=True),
        ) as app_perm,
    ):
        result = await engineering.get_build("bj1", member, db)

    assert result.data["id"] == "bj1"
    kb_perm.assert_awaited_once()
    app_perm.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_build_forbidden_without_application_or_kb_read(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_API_V2_ENABLED", True)
    monkeypatch.setattr(settings, "KNOWLEDGE_V2_BUILD_ENABLED", True)
    job = _job()
    release = _release()
    member = _member(member_id="outsider")
    db = AsyncMock()

    async def _get(model, oid):
        if model is KnowledgeBuildJob:
            return job
        if model is KnowledgeApplicationRelease:
            return release
        return None

    db.get = AsyncMock(side_effect=_get)

    with (
        patch(
            "app.api.v2.engineering.permission_service.has_kb_permission",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "app.api.v2.engineering.permission_service.has_application_permission",
            new=AsyncMock(return_value=False),
        ),
        pytest.raises(ForbiddenError),
    ):
        await engineering.get_build("bj1", member, db)

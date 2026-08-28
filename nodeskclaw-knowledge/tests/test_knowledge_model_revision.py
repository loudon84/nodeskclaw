"""Knowledge model revision tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_model_service


MEMBER = KnowledgePrincipal(
    user_id="user-1",
    member_id="member-1",
    org_id="org-1",
    name="Tester",
)


@pytest.mark.asyncio
async def test_update_model_creates_draft_revision_without_overwriting_active(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V23_MODEL_REVISION_ENABLED", True)
    model = SimpleNamespace(
        id="m1",
        org_id="org-1",
        name="Model",
        description=None,
        version=1,
        active_revision_id="rev-1",
        entities=[{"name": "A"}],
        relations=[],
        terms=[],
        extraction_policy={},
        deleted_at=None,
    )
    active_revision = SimpleNamespace(
        id="rev-1",
        deleted_at=None,
        entities=[{"name": "A"}],
        relations=[],
        terms=[],
        extraction_policy={},
        revision_number=1,
    )
    db = MagicMock()
    db.get = AsyncMock(side_effect=lambda _cls, _id: model if _id == "m1" else active_revision)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    async def _fake_create_revision(db_arg, member, model_arg, **kwargs):
        assert kwargs["status"] == "draft"
        assert kwargs["entities"] == [{"name": "B"}]
        return SimpleNamespace(id="rev-2", revision_number=2, status="draft")

    monkeypatch.setattr(knowledge_model_service, "_create_revision", _fake_create_revision)
    monkeypatch.setattr(knowledge_model_service, "get_active_revision", AsyncMock(return_value=active_revision))

    updated = await knowledge_model_service.update_model(
        db,
        MEMBER,
        "m1",
        entities=[{"name": "B"}],
    )
    assert updated is model
    assert model.entities == [{"name": "A"}]


@pytest.mark.asyncio
async def test_publish_revision_syncs_active_payload(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V23_MODEL_REVISION_ENABLED", True)
    model = SimpleNamespace(
        id="m1",
        org_id="org-1",
        name="Model",
        version=1,
        active_revision_id="rev-1",
        entities=[],
        relations=[],
        terms=[],
        extraction_policy={},
        deleted_at=None,
    )
    draft = SimpleNamespace(
        id="rev-2",
        org_id="org-1",
        knowledge_model_id="m1",
        deleted_at=None,
        status="draft",
        revision_number=2,
        entities=[{"name": "B"}],
        relations=[{"from": "A", "to": "B"}],
        terms=[{"term": "付款"}],
        extraction_policy={"mode": "strict"},
        published_at=None,
    )
    db = MagicMock()
    db.get = AsyncMock(return_value=model)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    monkeypatch.setattr(knowledge_model_service, "get_revision", AsyncMock(return_value=draft))

    published = await knowledge_model_service.publish_revision(db, MEMBER, "m1", "rev-2")
    assert published.active_revision_id == "rev-2"
    assert published.entities == [{"name": "B"}]
    assert draft.status == "active"
    assert draft.published_at is not None


@pytest.mark.asyncio
async def test_publish_revision_archives_previous_active(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V23_MODEL_REVISION_ENABLED", True)
    model = SimpleNamespace(
        id="m1",
        org_id="org-1",
        name="Model",
        version=1,
        active_revision_id="rev-1",
        entities=[{"name": "A"}],
        relations=[],
        terms=[],
        extraction_policy={},
        deleted_at=None,
    )
    previous_active = SimpleNamespace(
        id="rev-1",
        org_id="org-1",
        knowledge_model_id="m1",
        deleted_at=None,
        status="active",
        revision_number=1,
        entities=[{"name": "A"}],
        relations=[],
        terms=[],
        extraction_policy={},
        published_at="2026-01-01T00:00:00+00:00",
    )
    draft = SimpleNamespace(
        id="rev-2",
        org_id="org-1",
        knowledge_model_id="m1",
        deleted_at=None,
        status="draft",
        revision_number=2,
        entities=[{"name": "B"}],
        relations=[],
        terms=[],
        extraction_policy={},
        published_at=None,
    )
    db = MagicMock()
    db.get = AsyncMock(return_value=model)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[previous_active])))
    monkeypatch.setattr(knowledge_model_service, "get_revision", AsyncMock(return_value=draft))

    await knowledge_model_service.publish_revision(db, MEMBER, "m1", "rev-2")
    assert previous_active.status == "archived"
    assert draft.status == "active"
    assert model.active_revision_id == "rev-2"

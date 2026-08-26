"""KnowledgeApplication permission and set binding tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.models.enums import ApplicationPermission, ApplicationStatus
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_application_service, knowledge_set_service
from app.services.permission_service import has_application_permission


def _member(**kwargs) -> KnowledgePrincipal:
    base = dict(
        user_id="u1",
        member_id="m1",
        org_id="o1",
        name="User",
        department="eng",
        member_role="member",
        is_active=True,
        is_super_admin=False,
    )
    base.update(kwargs)
    return KnowledgePrincipal(**base)


@pytest.mark.asyncio
async def test_owner_has_application_use():
    db = AsyncMock()
    app = SimpleNamespace(
        id="app1",
        org_id="o1",
        owner_member_id="m1",
        deleted_at=None,
        status=ApplicationStatus.active.value,
    )
    assert await has_application_permission(db, _member(), app, ApplicationPermission.use.value) is True


@pytest.mark.asyncio
async def test_non_owner_without_acl_denied():
    class _Result:
        def scalars(self):
            return self

        def all(self):
            return []

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result())
    app = SimpleNamespace(
        id="app1",
        org_id="o1",
        owner_member_id="other",
        deleted_at=None,
    )
    assert await has_application_permission(db, _member(), app, ApplicationPermission.use.value) is False


@pytest.mark.asyncio
async def test_bind_knowledge_base_allows_embedding_mismatch():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None))
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()

    ks = SimpleNamespace(id="set1", embedding_model="model-a", org_id="o1", deleted_at=None)
    kb = SimpleNamespace(id="kb1", embedding_model="model-b", org_id="o1", deleted_at=None)

    with (
        patch(
            "app.services.knowledge_set_service.get_knowledge_set",
            new=AsyncMock(return_value=ks),
        ),
        patch(
            "app.services.knowledge_set_service.has_set_permission",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "app.services.knowledge_set_service.knowledge_base_service.get_knowledge_base",
            new=AsyncMock(return_value=kb),
        ),
        patch("app.services.knowledge_set_service.write_audit", new=AsyncMock()),
    ):
        item = await knowledge_set_service.bind_knowledge_base(db, _member(), "set1", "kb1")

    assert item.knowledge_base_id == "kb1"
    assert item.knowledge_set_id == "set1"


@pytest.mark.asyncio
async def test_create_application_requires_flag(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V2_APPLICATION_ENABLED", False)
    with pytest.raises(BadRequestError) as exc:
        await knowledge_application_service.create_application(
            AsyncMock(), _member(), name="app"
        )
    assert exc.value.message_key == "errors.knowledge.application_disabled"

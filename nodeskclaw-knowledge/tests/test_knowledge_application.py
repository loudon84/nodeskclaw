"""KnowledgeApplication permission and set binding tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.models.enums import ApplicationPermission, ApplicationStatus, KnowledgeSetStatus
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_application_service, knowledge_set_service, retrieval_service
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


@pytest.mark.asyncio
async def test_retrieve_for_application_merges_all_bound_sets(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V2_APPLICATION_ENABLED", True)
    db = AsyncMock()
    member = _member()
    ragflow = AsyncMock()
    app = SimpleNamespace(
        id="app1",
        org_id="o1",
        owner_member_id="m1",
        deleted_at=None,
        status=ApplicationStatus.active.value,
        answer_model="gpt",
        active_profile_id=None,
    )
    set_a = SimpleNamespace(id="set_a", status=KnowledgeSetStatus.active.value, org_id="o1", deleted_at=None)
    set_b = SimpleNamespace(id="set_b", status=KnowledgeSetStatus.active.value, org_id="o1", deleted_at=None)
    kb_a = SimpleNamespace(id="kb_a", metadata_schema=None)
    kb_b = SimpleNamespace(id="kb_b", metadata_schema=None)

    async def _get_set(_db, _member, set_id):
        return {"set_a": set_a, "set_b": set_b}[set_id]

    async def _list_kbs(_db, _member, set_id):
        return {"set_a": [kb_a], "set_b": [kb_b]}[set_id]

    async def _list_items(_db, _member, set_id):
        return {
            "set_a": [SimpleNamespace(knowledge_base_id="kb_a", weight=1.0)],
            "set_b": [SimpleNamespace(knowledge_base_id="kb_b", weight=2.0)],
        }[set_id]

    with (
        patch(
            "app.services.knowledge_application_service.get_application",
            new=AsyncMock(return_value=app),
        ),
        patch(
            "app.services.retrieval_service.has_application_permission",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "app.services.knowledge_application_service.list_bound_set_ids",
            new=AsyncMock(return_value=["set_a", "set_b"]),
        ),
        patch(
            "app.services.retrieval_service.knowledge_set_service.get_knowledge_set",
            new=AsyncMock(side_effect=_get_set),
        ),
        patch(
            "app.services.retrieval_service.has_set_permission",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "app.services.retrieval_service.knowledge_set_service.list_bound_knowledge_bases",
            new=AsyncMock(side_effect=_list_kbs),
        ),
        patch(
            "app.services.retrieval_service.knowledge_set_service.list_set_items",
            new=AsyncMock(side_effect=_list_items),
        ),
        patch(
            "app.services.retrieval_service._retrieve_for_set",
            new=AsyncMock(return_value={"chunks": [], "status": "empty"}),
        ) as retrieve_set,
    ):
        result = await retrieval_service.retrieve_for_application(
            db, member, ragflow, application_id="app1", query="hello"
        )

    retrieve_set.assert_awaited_once()
    kwargs = retrieve_set.await_args.kwargs
    assert {kb.id for kb in kwargs["kbs_override"]} == {"kb_a", "kb_b"}
    assert {i.knowledge_base_id for i in kwargs["set_items_override"]} == {"kb_a", "kb_b"}
    assert kwargs["bump_set_ids"] == ["set_a", "set_b"]
    assert result["application_id"] == "app1"
    assert result["knowledge_set_ids"] == ["set_a", "set_b"]


@pytest.mark.asyncio
async def test_retrieve_for_application_skips_disabled_set(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V2_APPLICATION_ENABLED", True)
    db = AsyncMock()
    member = _member()
    app = SimpleNamespace(
        id="app1",
        org_id="o1",
        owner_member_id="m1",
        deleted_at=None,
        status=ApplicationStatus.active.value,
        answer_model=None,
        active_profile_id=None,
    )
    set_ok = SimpleNamespace(id="set_ok", status=KnowledgeSetStatus.active.value, org_id="o1", deleted_at=None)
    set_off = SimpleNamespace(id="set_off", status=KnowledgeSetStatus.disabled.value, org_id="o1", deleted_at=None)
    kb = SimpleNamespace(id="kb1", metadata_schema=None)

    async def _get_set(_db, _member, set_id):
        return {"set_ok": set_ok, "set_off": set_off}[set_id]

    with (
        patch(
            "app.services.knowledge_application_service.get_application",
            new=AsyncMock(return_value=app),
        ),
        patch(
            "app.services.retrieval_service.has_application_permission",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "app.services.knowledge_application_service.list_bound_set_ids",
            new=AsyncMock(return_value=["set_off", "set_ok"]),
        ),
        patch(
            "app.services.retrieval_service.knowledge_set_service.get_knowledge_set",
            new=AsyncMock(side_effect=_get_set),
        ),
        patch(
            "app.services.retrieval_service.has_set_permission",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "app.services.retrieval_service.knowledge_set_service.list_bound_knowledge_bases",
            new=AsyncMock(return_value=[kb]),
        ),
        patch(
            "app.services.retrieval_service.knowledge_set_service.list_set_items",
            new=AsyncMock(return_value=[SimpleNamespace(knowledge_base_id="kb1", weight=1.0)]),
        ),
        patch(
            "app.services.retrieval_service._retrieve_for_set",
            new=AsyncMock(return_value={"chunks": []}),
        ) as retrieve_set,
    ):
        await retrieval_service.retrieve_for_application(
            db, member, AsyncMock(), application_id="app1", query="q"
        )

    assert retrieve_set.await_args.kwargs["bump_set_ids"] == ["set_ok"]
    assert retrieve_set.await_args.kwargs["knowledge_set_id"] == "set_ok"

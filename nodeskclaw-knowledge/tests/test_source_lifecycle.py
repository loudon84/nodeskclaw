"""SourceFile lifecycle: archive, unarchive, version activate, set disabled."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError, ForbiddenError
from app.models.enums import AccessPlanKind, KnowledgeSetStatus
from app.schemas.principal import KnowledgePrincipal
from app.services import permission_service, source_lifecycle_service
from app.services.chat_service import create_session
from app.services.retrieval_service import retrieve


def _member(**kwargs) -> KnowledgePrincipal:
    base = dict(
        user_id="u1",
        member_id="m1",
        org_id="o1",
        name="Zhang",
        department="sales",
        member_role="member",
        is_active=True,
        is_super_admin=False,
    )
    base.update(kwargs)
    return KnowledgePrincipal(**base)


def _sf(**kwargs):
    data = dict(
        id="sf1",
        org_id="o1",
        knowledge_base_id="kb1",
        owner_member_id="m1",
        active_version_id="v3",
        status="active",
        archived_at=None,
        deleted_at=None,
    )
    data.update(kwargs)
    return SimpleNamespace(**data)


def _version(**kwargs):
    data = dict(
        id="v2",
        source_file_id="sf1",
        parse_status="superseded",
        ragflow_document_id="doc-v2",
        deleted_at=None,
        activated_at=None,
        superseded_at=datetime.now(UTC),
    )
    data.update(kwargs)
    return SimpleNamespace(**data)


@pytest.mark.asyncio
async def test_archive_sets_archived_at_and_disables_ragflow():
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.get = AsyncMock(return_value=_version(id="v3", parse_status="active", ragflow_document_id="doc-v3"))
    ragflow = AsyncMock()
    member = _member()
    sf = _sf()
    kb = SimpleNamespace(id="kb1", ragflow_dataset_id="ds1", deleted_at=None, org_id="o1")

    with (
        patch(
            "app.services.source_lifecycle_service.source_file_service.get_source_file",
            new=AsyncMock(return_value=sf),
        ),
        patch(
            "app.services.source_lifecycle_service._require_update_or_manage",
            new=AsyncMock(),
        ),
        patch(
            "app.services.source_lifecycle_service.knowledge_base_service.get_knowledge_base",
            new=AsyncMock(return_value=kb),
        ),
        patch(
            "app.services.source_lifecycle_service.runtime_binding_service.get_dataset_id",
            new=AsyncMock(return_value="ds1"),
        ),
        patch("app.services.source_lifecycle_service.write_audit", new=AsyncMock()),
    ):
        result = await source_lifecycle_service.archive_source_file(db, member, ragflow, "sf1")

    assert result.archived_at is not None
    ragflow.set_document_enabled.assert_awaited_once_with("ds1", "doc-v3", False)
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_unarchive_clears_archived_at_and_enables_active():
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.get = AsyncMock(return_value=_version(id="v3", parse_status="active", ragflow_document_id="doc-v3"))
    ragflow = AsyncMock()
    member = _member()
    sf = _sf(archived_at=datetime.now(UTC))
    kb = SimpleNamespace(id="kb1", ragflow_dataset_id="ds1", deleted_at=None, org_id="o1")

    with (
        patch(
            "app.services.source_lifecycle_service.source_file_service.get_source_file",
            new=AsyncMock(return_value=sf),
        ),
        patch(
            "app.services.source_lifecycle_service._require_update_or_manage",
            new=AsyncMock(),
        ),
        patch(
            "app.services.source_lifecycle_service.knowledge_base_service.get_knowledge_base",
            new=AsyncMock(return_value=kb),
        ),
        patch(
            "app.services.source_lifecycle_service.runtime_binding_service.get_dataset_id",
            new=AsyncMock(return_value="ds1"),
        ),
        patch("app.services.source_lifecycle_service.write_audit", new=AsyncMock()),
    ):
        result = await source_lifecycle_service.unarchive_source_file(db, member, ragflow, "sf1")

    assert result.archived_at is None
    ragflow.set_document_enabled.assert_awaited_once_with("ds1", "doc-v3", True)


@pytest.mark.asyncio
async def test_activate_version_rollback_blue_green():
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    target = _version(id="v2", parse_status="superseded", ragflow_document_id="doc-v2")
    old = _version(id="v3", parse_status="active", ragflow_document_id="doc-v3", superseded_at=None)

    async def _get(_model, oid):
        return {target.id: target, old.id: old}[oid]

    db.get = AsyncMock(side_effect=_get)
    ragflow = AsyncMock()
    member = _member()
    sf = _sf(active_version_id="v3")
    kb = SimpleNamespace(id="kb1", ragflow_dataset_id="ds1", deleted_at=None, org_id="o1")

    with (
        patch(
            "app.services.source_lifecycle_service.source_file_service.get_source_file",
            new=AsyncMock(return_value=sf),
        ),
        patch(
            "app.services.source_lifecycle_service._require_update_or_manage",
            new=AsyncMock(),
        ),
        patch(
            "app.services.source_lifecycle_service.knowledge_base_service.get_knowledge_base",
            new=AsyncMock(return_value=kb),
        ),
        patch(
            "app.services.source_lifecycle_service.runtime_binding_service.require_dataset_id",
            new=AsyncMock(return_value="ds1"),
        ),
        patch("app.services.source_lifecycle_service.write_audit", new=AsyncMock()),
    ):
        result = await source_lifecycle_service.activate_source_file_version(
            db, member, ragflow, "sf1", "v2"
        )

    assert result.active_version_id == "v2"
    assert target.parse_status == "active"
    assert old.parse_status == "superseded"
    assert ragflow.set_document_enabled.await_args_list[0].args == ("ds1", "doc-v2", True)
    assert ragflow.set_document_enabled.await_args_list[1].args == ("ds1", "doc-v3", False)


@pytest.mark.asyncio
async def test_activate_rejects_failed_version():
    db = MagicMock()
    ragflow = AsyncMock()
    member = _member()
    sf = _sf()
    failed = _version(id="v1", parse_status="failed", ragflow_document_id="doc-v1")
    db.get = AsyncMock(return_value=failed)

    with (
        patch(
            "app.services.source_lifecycle_service.source_file_service.get_source_file",
            new=AsyncMock(return_value=sf),
        ),
        patch(
            "app.services.source_lifecycle_service._require_update_or_manage",
            new=AsyncMock(),
        ),
        pytest.raises(BadRequestError) as exc,
    ):
        await source_lifecycle_service.activate_source_file_version(db, member, ragflow, "sf1", "v1")

    assert exc.value.message_key == "errors.knowledge.version_not_activatable"


@pytest.mark.asyncio
async def test_activate_rejects_archived_file():
    db = MagicMock()
    ragflow = AsyncMock()
    member = _member()
    sf = _sf(archived_at=datetime.now(UTC))

    with (
        patch(
            "app.services.source_lifecycle_service.source_file_service.get_source_file",
            new=AsyncMock(return_value=sf),
        ),
        patch(
            "app.services.source_lifecycle_service._require_update_or_manage",
            new=AsyncMock(),
        ),
        pytest.raises(BadRequestError) as exc,
    ):
        await source_lifecycle_service.activate_source_file_version(db, member, ragflow, "sf1", "v2")

    assert exc.value.message_key == "errors.knowledge.source_file_archived"


@pytest.mark.asyncio
async def test_retrieve_rejects_disabled_set():
    db = MagicMock()
    ragflow = AsyncMock()
    member = _member()
    ks = SimpleNamespace(id="set1", status=KnowledgeSetStatus.disabled.value, org_id="o1")

    with (
        patch(
            "app.services.retrieval_service.knowledge_set_service.get_knowledge_set",
            new=AsyncMock(return_value=ks),
        ),
        pytest.raises(ForbiddenError) as exc,
    ):
        await retrieve(db, member, ragflow, knowledge_set_id="set1", query="q")

    assert exc.value.message_key == "errors.knowledge.set_disabled"


@pytest.mark.asyncio
async def test_create_session_rejects_disabled_set():
    db = MagicMock()
    member = _member()
    ks = SimpleNamespace(id="set1", status=KnowledgeSetStatus.disabled.value, org_id="o1")

    with (
        patch(
            "app.services.chat_service.knowledge_set_service.get_knowledge_set",
            new=AsyncMock(return_value=ks),
        ),
        pytest.raises(ForbiddenError) as exc,
    ):
        await create_session(db, member, knowledge_set_id="set1")

    assert exc.value.message_key == "errors.knowledge.set_disabled"


@pytest.mark.asyncio
async def test_build_access_plan_excludes_archived_files(monkeypatch):
    member = _member(is_super_admin=True)
    kb = SimpleNamespace(
        id="kb1",
        org_id="o1",
        status="active",
        ragflow_dataset_id="ds1",
        deleted_at=None,
        owner_member_id="m1",
    )
    active_sf = _sf(id="sf-active", archived_at=None, active_version_id="va")

    captured = {}

    class _Result:
        def scalars(self):
            return self

        def all(self):
            return captured["files"]

        def scalar_one_or_none(self):
            return None

    class _Db:
        async def execute(self, stmt):
            captured["stmt"] = str(stmt)
            sql = str(stmt)
            if "knowledge_runtime_bindings" in sql or "KnowledgeRuntimeBinding" in sql:
                return _Result()
            captured["files"] = [active_sf]
            return _Result()

        async def get(self, model, oid):
            return SimpleNamespace(
                id=oid,
                ragflow_document_id=f"doc-{oid}",
                deleted_at=None,
            )

    async def fake_snapshot(*_args, **_kwargs):
        return SimpleNamespace(
            has_kb_permission=lambda *_a, **_k: True,
            has_file_permission=lambda *_a, **_k: True,
        )

    monkeypatch.setattr(
        "app.services.permission_snapshot_service.load_permission_snapshot",
        fake_snapshot,
    )
    plan = await permission_service.build_access_plan(_Db(), member, [kb])
    assert "archived_at" in captured["stmt"].lower()
    assert plan.kind == AccessPlanKind.full_access
    assert plan.source_file_ids == ["sf-active"]

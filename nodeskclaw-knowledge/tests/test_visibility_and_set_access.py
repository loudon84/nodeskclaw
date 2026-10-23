"""KB visibility seed ACL (read+upload) and Set retrieval KB-bypass tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import AccessPlanKind, AclEffect, KbPermission, SubjectType, Visibility
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_base_service, permission_service
from app.services.acl_templates import visibility_acl_specs


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


def test_visibility_acl_specs_org_and_dept_include_read_and_upload():
    specs = visibility_acl_specs(
        Visibility.organization.value,
        org_id="o1",
        department="sales",
        permissions=[KbPermission.read.value, KbPermission.upload.value],
    )
    assert (SubjectType.organization.value, "o1", "read") in specs
    assert (SubjectType.organization.value, "o1", "upload") in specs

    specs_dept = visibility_acl_specs(
        Visibility.department.value,
        org_id="o1",
        department="sales",
        permissions=[KbPermission.read.value, KbPermission.upload.value],
    )
    assert (SubjectType.department.value, "sales", "read") in specs_dept
    assert (SubjectType.department.value, "sales", "upload") in specs_dept

    assert visibility_acl_specs(
        Visibility.private.value,
        org_id="o1",
        department="sales",
        permissions=[KbPermission.read.value, KbPermission.upload.value],
    ) == []


def test_seed_visibility_acl_adds_read_and_upload(monkeypatch):
    added: list[SimpleNamespace] = []

    class FakeAcl:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
            added.append(self)

    monkeypatch.setattr(knowledge_base_service, "KnowledgeBaseAcl", FakeAcl)
    db = MagicMock()
    member = _member()
    knowledge_base_service._seed_visibility_acl(
        db,
        knowledge_base_id="kb1",
        visibility=Visibility.organization.value,
        member=member,
    )
    perms = {(a.subject_type, a.subject_id, a.permission) for a in added}
    assert (SubjectType.organization.value, "o1", "read") in perms
    assert (SubjectType.organization.value, "o1", "upload") in perms
    assert all(a.effect == AclEffect.allow.value for a in added)


@pytest.mark.asyncio
async def test_replace_visibility_seed_acl_soft_deletes_old_seeds(monkeypatch):
    soft_deleted: list[str] = []
    old_acl = SimpleNamespace(
        id="acl-old",
        subject_type=SubjectType.organization.value,
        subject_id="o1",
        permission="read",
        effect=AclEffect.allow.value,
        soft_delete=lambda: soft_deleted.append("acl-old"),
    )
    manual_acl = SimpleNamespace(
        id="acl-manual",
        subject_type=SubjectType.member.value,
        subject_id="m2",
        permission="upload",
        effect=AclEffect.allow.value,
        soft_delete=lambda: soft_deleted.append("acl-manual"),
    )

    class Result:
        def scalars(self):
            return self

        def all(self):
            # select filter already limited to org/dept + read/upload; only return old seed
            return [old_acl]

    db = AsyncMock()
    db.execute = AsyncMock(return_value=Result())
    kb = SimpleNamespace(id="kb1", acl_version=1, visibility="organization")
    member = _member()
    seeded: list[tuple] = []

    def fake_seed(_db, *, knowledge_base_id, visibility, member):
        seeded.append((knowledge_base_id, visibility, member.member_id))

    monkeypatch.setattr(knowledge_base_service, "_seed_visibility_acl", fake_seed)
    await knowledge_base_service._replace_visibility_seed_acl(
        db,
        kb=kb,
        visibility=Visibility.private.value,
        member=member,
    )
    assert soft_deleted == ["acl-old"]
    assert "acl-manual" not in soft_deleted
    assert seeded == [("kb1", Visibility.private.value, "m1")]
    assert kb.acl_version == 2


@pytest.mark.asyncio
async def test_build_access_plan_for_set_bypasses_kb_read(monkeypatch):
    member = _member(member_id="m2")
    kb = SimpleNamespace(id="kb1", status="active", org_id="o1")
    sf = SimpleNamespace(
        id="sf1",
        knowledge_base_id="kb1",
        org_id="o1",
        status="active",
        archived_at=None,
        active_version_id="v1",
        deleted_at=None,
    )

    class FakeSnapshot:
        file_acls = {}
        file_owners = {"sf1": "owner-m"}

        def has_kb_permission(self, _kb_id, _permission):
            return False

        def has_file_permission(self, _sf_id, _permission):
            return False

    async def fake_load(*_args, **_kwargs):
        return FakeSnapshot()

    class FileResult:
        def scalars(self):
            return self

        def all(self):
            return [sf]

    db = AsyncMock()
    db.execute = AsyncMock(return_value=FileResult())
    db.get = AsyncMock(
        return_value=SimpleNamespace(
            id="v1",
            ragflow_document_id="doc1",
            deleted_at=None,
        )
    )

    monkeypatch.setattr(
        "app.services.permission_snapshot_service.load_permission_snapshot",
        fake_load,
    )
    monkeypatch.setattr(
        "app.services.runtime_binding_service.get_dataset_id",
        AsyncMock(return_value="ds1"),
    )

    denied = await permission_service.build_access_plan(db, member, [kb])
    assert denied.kind == AccessPlanKind.no_access

    allowed = await permission_service.build_access_plan_for_set(db, member, [kb])
    assert allowed.kind == AccessPlanKind.full_access
    assert allowed.dataset_ids == ["ds1"]
    assert "sf1" in allowed.source_file_ids


@pytest.mark.asyncio
async def test_build_access_plan_for_set_respects_file_deny(monkeypatch):
    member = _member(member_id="m2")
    kb = SimpleNamespace(id="kb1", status="active", org_id="o1")
    sf = SimpleNamespace(
        id="sf1",
        knowledge_base_id="kb1",
        org_id="o1",
        status="active",
        archived_at=None,
        active_version_id="v1",
        deleted_at=None,
    )
    deny_acl = SimpleNamespace(
        subject_type=SubjectType.member.value,
        subject_id="m2",
        permission="read",
        effect=AclEffect.deny.value,
    )

    class FakeSnapshot:
        file_acls = {"sf1": [deny_acl]}
        file_owners = {"sf1": "owner-m"}

        def has_kb_permission(self, _kb_id, _permission):
            return False

    async def fake_load(*_args, **_kwargs):
        return FakeSnapshot()

    class FileResult:
        def scalars(self):
            return self

        def all(self):
            return [sf]

    db = AsyncMock()
    db.execute = AsyncMock(return_value=FileResult())
    monkeypatch.setattr(
        "app.services.permission_snapshot_service.load_permission_snapshot",
        fake_load,
    )
    monkeypatch.setattr(
        "app.services.runtime_binding_service.get_dataset_id",
        AsyncMock(return_value="ds1"),
    )

    plan = await permission_service.build_access_plan_for_set(db, member, [kb])
    assert plan.kind == AccessPlanKind.filtered_access
    assert plan.source_file_ids == []
    assert plan.document_ids == []

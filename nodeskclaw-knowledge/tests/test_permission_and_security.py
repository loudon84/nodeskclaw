"""ACL / AccessPlan unit tests with mocked DB rows."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.ragflow.models import RagflowChunk
from app.models.enums import AccessPlanKind, AclEffect, SubjectType
from app.schemas.principal import KnowledgePrincipal
from app.services import permission_service
from app.services.chunk_security_service import ActiveDocumentIdentity, clean_chunks
from app.services.ingestion_service import build_meta_fields


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


def test_build_meta_fields_identity_only():
    meta = build_meta_fields(
        source_file_id="sf1",
        file_version_id="sfv1",
        knowledge_base_id="kb1",
        org_id="o1",
    )
    assert meta == {
        "nk_source_file_id": "sf1",
        "nk_file_version_id": "sfv1",
        "nk_knowledge_base_id": "kb1",
        "nk_org_id": "o1",
        "nk_metadata_revision": "0",
    }
    assert "allowed_users" not in meta
    assert not any(k.startswith("biz_") for k in meta)


def test_subject_match_member_and_department():
    member = _member()
    acl_member = SimpleNamespace(subject_type=SubjectType.member.value, subject_id="m1", permission="read")
    acl_dept = SimpleNamespace(subject_type=SubjectType.department.value, subject_id="sales", permission="read")
    acl_other = SimpleNamespace(subject_type=SubjectType.member.value, subject_id="m2", permission="read")
    assert permission_service._subject_matches(acl_member, member) is True
    assert permission_service._subject_matches(acl_dept, member) is True
    assert permission_service._subject_matches(acl_other, member) is False


def test_resolve_permission_deny_wins():
    member = _member()
    acls = [
        SimpleNamespace(
            subject_type=SubjectType.organization.value,
            subject_id="o1",
            permission="read",
            effect=AclEffect.allow.value,
        ),
        SimpleNamespace(
            subject_type=SubjectType.member.value,
            subject_id="m1",
            permission="read",
            effect=AclEffect.deny.value,
        ),
    ]
    assert permission_service._resolve_permission(acls, member, "read") is False


def test_resolve_permission_member_over_org():
    member = _member()
    acls = [
        SimpleNamespace(
            subject_type=SubjectType.organization.value,
            subject_id="o1",
            permission="read",
            effect=AclEffect.allow.value,
        ),
        SimpleNamespace(
            subject_type=SubjectType.member.value,
            subject_id="m1",
            permission="read",
            effect=AclEffect.allow.value,
        ),
    ]
    assert permission_service._resolve_permission(acls, member, "read") is True


@pytest.mark.asyncio
async def test_clean_chunks_drops_unauthorized_and_missing_identity():
    db = MagicMock()
    ragflow = AsyncMock()
    chunks = [
        RagflowChunk(id="c1", content="a", document_id="d1", document_metadata={"nk_source_file_id": "sf_ok"}),
        RagflowChunk(id="c2", content="b", document_id="d2", document_metadata={"nk_source_file_id": "sf_deny"}),
        RagflowChunk(id="c3", content="c", document_id="d3", document_metadata={}),
    ]

    identity_ok = SimpleNamespace(
        source_file_id="sf_ok",
        file_version_id="v1",
        knowledge_base_id="kb1",
        org_id="o1",
        active_version_id="v1",
    )

    async def fake_build_map(_db, document_ids):
        if "d1" in document_ids:
            return {"d1": identity_ok}
        return {}

    with patch(
        "app.services.chunk_security_service._build_active_document_map",
        new=AsyncMock(side_effect=fake_build_map),
    ):
        safe, filtered = await clean_chunks(
            db,
            ragflow,
            chunks,
            allowed_source_file_ids={"sf_ok"},
        )
    assert [c.id for c in safe] == ["c1"]
    assert filtered == 2


@pytest.mark.asyncio
async def test_build_access_plan_no_access(monkeypatch):
    db = AsyncMock()
    member = _member()
    kb = SimpleNamespace(id="kb1", ragflow_dataset_id="ds1", org_id="o1", status="active")

    class FakeSnapshot:
        def has_kb_permission(self, _kb_id, _permission):
            return False

    async def fake_load(*_args, **_kwargs):
        return FakeSnapshot()

    monkeypatch.setattr(
        "app.services.permission_snapshot_service.load_permission_snapshot",
        fake_load,
    )
    plan = await permission_service.build_access_plan(db, member, [kb])
    assert plan.kind == AccessPlanKind.no_access


@pytest.mark.asyncio
async def test_skill_run_auth_proofs_use_has_set_permission(monkeypatch):
    from app.api.v2.skill_run_auth import SkillRunAuthProofRequest, issue_skill_run_auth_proofs

    db = AsyncMock()
    ks_allowed = SimpleNamespace(id="ks-1", org_id="o1", deleted_at=None, updated_at=None)
    ks_denied = SimpleNamespace(id="ks-2", org_id="o1", deleted_at=None, updated_at=None)

    async def fake_get(_model, pk):
        return {"ks-1": ks_allowed, "ks-2": ks_denied}.get(pk)

    db.get = AsyncMock(side_effect=fake_get)

    async def fake_has_perm(_db, _member, ks, _perm):
        return ks.id == "ks-1"

    monkeypatch.setattr("app.api.v2.skill_run_auth.permission_service.has_set_permission", fake_has_perm)

    resp = await issue_skill_run_auth_proofs(
        SkillRunAuthProofRequest(org_id="o1", member_id="m1", knowledge_set_ids=["ks-1", "ks-2"]),
        db=db,
        _=None,
    )
    proofs = {item.set_id: item for item in resp.data.proofs}
    assert proofs["ks-1"].allowed is True
    assert proofs["ks-2"].allowed is False
    assert proofs["ks-1"].auth_version


def test_service_token_cannot_call_tool_search():
    import inspect

    from app.api import agent_tools
    from app.core.deps import get_member_context, require_knowledge_service_token

    params = inspect.signature(agent_tools.tool_search).parameters
    assert "member" in params
    assert get_member_context is not require_knowledge_service_token


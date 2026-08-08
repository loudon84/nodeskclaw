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
    }
    assert "allowed_users" not in meta


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

    async def fake_has_kb(*_args, **_kwargs):
        return False

    monkeypatch.setattr(permission_service, "has_kb_permission", fake_has_kb)
    plan = await permission_service.build_access_plan(db, member, [kb])
    assert plan.kind == AccessPlanKind.no_access

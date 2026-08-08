"""Retrieval Profile publish switches ACTIVE/ARCHIVED."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError
from app.models.enums import ProfileStatus
from app.schemas.principal import KnowledgePrincipal
from app.services import retrieval_profile_service
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


def _profile(**kwargs):
    data = dict(
        id="p1",
        knowledge_set_id="set1",
        version=1,
        config={"top_n": 8, "failure_policy": "fail_closed"},
        status=ProfileStatus.draft.value,
        created_by_member_id="m1",
        activated_at=None,
        deleted_at=None,
    )
    data.update(kwargs)
    return SimpleNamespace(**data)


@pytest.mark.asyncio
async def test_publish_archives_previous_active():
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    member = _member()
    draft = _profile(id="p2", version=2, status=ProfileStatus.draft.value)
    active = _profile(id="p1", version=1, status=ProfileStatus.active.value)

    with (
        patch(
            "app.services.retrieval_profile_service._get_profile_or_404",
            new=AsyncMock(return_value=draft),
        ),
        patch(
            "app.services.retrieval_profile_service._require_set_manage",
            new=AsyncMock(return_value=SimpleNamespace(id="set1")),
        ),
        patch(
            "app.services.retrieval_profile_service.get_active_profile",
            new=AsyncMock(return_value=active),
        ),
        patch("app.services.retrieval_profile_service.write_audit", new=AsyncMock()),
    ):
        result = await retrieval_profile_service.publish(db, member, "p2")

    assert result.status == ProfileStatus.active.value
    assert result.activated_at is not None
    assert active.status == ProfileStatus.archived.value
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_retrieve_requires_active_profile():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    ragflow = AsyncMock()
    member = SimpleNamespace(member_id="m1", org_id="o1")
    ks = SimpleNamespace(
        id="set1",
        org_id="o1",
        status="active",
        usage_count=0,
        last_used_at=None,
    )
    kbs = [SimpleNamespace(id="kb1", ragflow_dataset_id="ds1", metadata_schema=None)]

    with (
        patch("app.services.retrieval_service.knowledge_set_service.get_knowledge_set", new=AsyncMock(return_value=ks)),
        patch("app.services.retrieval_service.has_set_permission", new=AsyncMock(return_value=True)),
        patch(
            "app.services.retrieval_service.knowledge_set_service.list_bound_knowledge_bases",
            new=AsyncMock(return_value=kbs),
        ),
        patch(
            "app.services.retrieval_service.retrieval_profile_service.get_active_profile",
            new=AsyncMock(return_value=None),
        ),
    ):
        with pytest.raises(BadRequestError) as exc:
            await retrieve(db, member, ragflow, knowledge_set_id="set1", query="hello")

    assert exc.value.message_key == "errors.knowledge.profile_not_active"

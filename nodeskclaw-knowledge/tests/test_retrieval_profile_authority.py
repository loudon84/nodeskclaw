"""RetrievalProfile authority: v1 bridge and v2 patch semantics."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import knowledge_set_service, retrieval_profile_service


@pytest.mark.asyncio
async def test_v1_retrieval_config_syncs_active_profile():
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    row = SimpleNamespace(
        id="set1",
        org_id="o1",
        name="Set",
        retrieval_config={},
        deleted_at=None,
    )
    active = SimpleNamespace(id="p1", config={"top_n": 8}, deleted_at=None)
    member = SimpleNamespace(member_id="m1", org_id="o1")

    with (
        patch(
            "app.services.knowledge_set_service.get_knowledge_set",
            new=AsyncMock(return_value=row),
        ),
        patch("app.services.knowledge_set_service.has_set_permission", new=AsyncMock(return_value=True)),
        patch("app.services.knowledge_set_service.write_audit", new=AsyncMock()),
        patch(
            "app.services.retrieval_profile_service.sync_v1_retrieval_config_to_active_profile",
            new=AsyncMock(return_value=active),
        ) as sync,
        patch(
            "app.services.retrieval_profile_service.merge_profile_config",
            return_value={"top_n": 16},
        ),
    ):
        await knowledge_set_service.update_knowledge_set(
            db,
            member,
            "set1",
            retrieval_config={"top_n": 16},
        )

    sync.assert_awaited_once()
    assert row.retrieval_config == {"top_n": 16}


@pytest.mark.asyncio
async def test_v2_patch_retrieval_config_ignored():
    from app.schemas.knowledge import KnowledgeSetV2Update

    body = KnowledgeSetV2Update(name="new")
    assert not hasattr(body, "retrieval_config") or "retrieval_config" not in body.model_fields

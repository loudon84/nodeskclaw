"""API v2 Assets DTO — no Runtime Dataset / resource ids in responses."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v2 import assets
from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.schemas.knowledge import KnowledgeBaseV2Out, KnowledgeSetV2Create
from app.schemas.principal import KnowledgePrincipal


def _member() -> KnowledgePrincipal:
    return KnowledgePrincipal(
        user_id="u1",
        member_id="m1",
        org_id="o1",
        member_role="operator",
    )


def test_kb_v2_out_excludes_runtime_ids():
    kb = SimpleNamespace(
        id="kb1",
        org_id="o1",
        name="KB",
        description=None,
        embedding_model="bge-m3",
        chunk_method="naive",
        status="active",
        owner_member_id="m1",
        acl_version=1,
        visibility="private",
        tags=None,
        active_build_profile_id=None,
        knowledge_model_id=None,
        build_version=0,
        ragflow_dataset_id="secret-ds",
    )
    out = assets._kb_v2_out(kb)
    payload = out.model_dump()
    blob = str(payload).lower()
    assert "ragflow" not in blob
    assert "dataset" not in blob
    assert "resource_id" not in blob
    assert "secret-ds" not in blob
    assert isinstance(out, KnowledgeBaseV2Out)


def test_knowledge_set_v2_create_omits_embedding():
    body = KnowledgeSetV2Create(name="set-a")
    assert not hasattr(body, "embedding_model") or "embedding_model" not in body.model_fields_set


@pytest.mark.asyncio
async def test_create_kb_v2_disabled(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_API_V2_ENABLED", False)
    with pytest.raises(BadRequestError) as exc:
        await assets.create_knowledge_base_v2(
            MagicMock(name="n", description=None, embedding_model="bge-m3", chunk_method="naive", parser_config=None, visibility=SimpleNamespace(value="private"), tags=None),
            member=_member(),
            db=AsyncMock(),
            ragflow=AsyncMock(),
        )
    assert exc.value.message_key == "errors.knowledge.api_v2_disabled"


@pytest.mark.asyncio
async def test_create_set_v2_defaults_embedding(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_API_V2_ENABLED", True)
    created = SimpleNamespace(
        id="set1",
        org_id="o1",
        name="set-a",
        description=None,
        owner_member_id="m1",
        status="active",
        acl_version=1,
        visibility="private",
        retrieval_config=None,
        usage_count=0,
        last_used_at=None,
    )
    with (
        patch(
            "app.api.v2.assets.knowledge_set_service.create_knowledge_set",
            new=AsyncMock(return_value=created),
        ) as create,
        patch(
            "app.api.v2.assets.knowledge_set_service.list_set_items",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.api.v2.assets.retrieval_profile_service.get_active_profile",
            new=AsyncMock(return_value=None),
        ),
    ):
        result = await assets.create_knowledge_set_v2(
            KnowledgeSetV2Create(name="set-a"),
            member=_member(),
            db=AsyncMock(),
        )
    create.assert_awaited_once()
    assert create.await_args.kwargs["embedding_model"] == "bge-m3"
    assert result.data.name == "set-a"
    blob = str(result.data.model_dump()).lower()
    assert "ragflow" not in blob
    assert "dataset_id" not in blob

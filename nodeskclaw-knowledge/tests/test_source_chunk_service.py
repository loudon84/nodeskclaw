"""source_chunk_service unit tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ConflictError, ForbiddenError, ServiceUnavailableError
from app.integrations.ragflow.client import RagflowChunkPage
from app.integrations.ragflow.exceptions import RagflowError
from app.schemas.principal import KnowledgePrincipal
from app.services import source_chunk_service


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
        active_version_id="v1",
        status="active",
        archived_at=None,
        deleted_at=None,
    )
    data.update(kwargs)
    return SimpleNamespace(**data)


def _version(**kwargs):
    data = dict(
        id="v1",
        source_file_id="sf1",
        ragflow_document_id="doc1",
        deleted_at=None,
    )
    data.update(kwargs)
    return SimpleNamespace(**data)


@pytest.mark.asyncio
async def test_list_chunks_forwards_keywords_and_preserves_total():
    db = MagicMock()
    db.get = AsyncMock(return_value=_version())
    member = _member()
    ragflow = AsyncMock()
    ragflow.read_document_chunks_page = AsyncMock(
        return_value=RagflowChunkPage(
            chunks=[{"id": "c1", "content": "x", "available": True}],
            total=137,
            page=1,
            page_size=10,
        )
    )
    kb = SimpleNamespace(id="kb1", deleted_at=None)

    with (
        patch(
            "app.services.source_chunk_service.source_file_service.get_source_file",
            new=AsyncMock(return_value=_sf()),
        ),
        patch(
            "app.services.source_chunk_service.knowledge_base_service.get_knowledge_base",
            new=AsyncMock(return_value=kb),
        ),
        patch(
            "app.services.source_chunk_service.runtime_binding_service.get_dataset_id",
            new=AsyncMock(return_value="ds1"),
        ),
    ):
        page = await source_chunk_service.list_source_file_chunks(
            db,
            member,
            ragflow,
            "sf1",
            page=1,
            page_size=10,
            keywords="  LiteLLM  ",
        )

    ragflow.read_document_chunks_page.assert_awaited_once_with(
        "ds1",
        "doc1",
        page=1,
        page_size=10,
        keywords="LiteLLM",
    )
    assert page.total == 137
    assert page.file_version_id == "v1"
    assert page.items[0].id == "c1"
    assert page.items[0].available is True


@pytest.mark.asyncio
async def test_list_chunks_no_active_version():
    db = MagicMock()
    member = _member()
    ragflow = AsyncMock()
    with patch(
        "app.services.source_chunk_service.source_file_service.get_source_file",
        new=AsyncMock(return_value=_sf(active_version_id=None)),
    ):
        with pytest.raises(ConflictError) as ei:
            await source_chunk_service.list_source_file_chunks(db, member, ragflow, "sf1")
    assert ei.value.message_key == "errors.knowledge.chunk_no_active_version"
    ragflow.read_document_chunks_page.assert_not_called()


@pytest.mark.asyncio
async def test_set_available_stale_version_blocks_provider():
    db = MagicMock()
    member = _member()
    ragflow = AsyncMock()
    with (
        patch(
            "app.services.source_chunk_service.source_file_service.get_source_file",
            new=AsyncMock(return_value=_sf(active_version_id="v2")),
        ),
        patch(
            "app.services.source_chunk_service._require_update_or_manage",
            new=AsyncMock(),
        ),
    ):
        with pytest.raises(ConflictError) as ei:
            await source_chunk_service.set_source_file_chunk_available(
                db,
                member,
                ragflow,
                "sf1",
                "c1",
                file_version_id="v1",
                available=False,
            )
    assert ei.value.message_key == "errors.knowledge.chunk_version_conflict"
    ragflow.set_document_chunk_available.assert_not_called()


@pytest.mark.asyncio
async def test_set_available_forbidden_without_update_or_manage():
    db = MagicMock()
    member = _member()
    ragflow = AsyncMock()
    with (
        patch(
            "app.services.source_chunk_service.source_file_service.get_source_file",
            new=AsyncMock(return_value=_sf()),
        ),
        patch(
            "app.services.source_chunk_service._require_update_or_manage",
            new=AsyncMock(side_effect=ForbiddenError()),
        ),
    ):
        with pytest.raises(ForbiddenError):
            await source_chunk_service.set_source_file_chunk_available(
                db,
                member,
                ragflow,
                "sf1",
                "c1",
                file_version_id="v1",
                available=True,
            )
    ragflow.set_document_chunk_available.assert_not_called()


@pytest.mark.asyncio
async def test_set_available_success_audits():
    db = MagicMock()
    db.get = AsyncMock(return_value=_version())
    db.commit = AsyncMock()
    member = _member()
    ragflow = AsyncMock()
    ragflow.set_document_chunk_available = AsyncMock()
    kb = SimpleNamespace(id="kb1", deleted_at=None)

    with (
        patch(
            "app.services.source_chunk_service.source_file_service.get_source_file",
            new=AsyncMock(return_value=_sf()),
        ),
        patch(
            "app.services.source_chunk_service._require_update_or_manage",
            new=AsyncMock(),
        ),
        patch(
            "app.services.source_chunk_service.knowledge_base_service.get_knowledge_base",
            new=AsyncMock(return_value=kb),
        ),
        patch(
            "app.services.source_chunk_service.runtime_binding_service.get_dataset_id",
            new=AsyncMock(return_value="ds1"),
        ),
        patch(
            "app.services.source_chunk_service.write_audit",
            new=AsyncMock(),
        ) as audit,
    ):
        result = await source_chunk_service.set_source_file_chunk_available(
            db,
            member,
            ragflow,
            "sf1",
            "c1",
            file_version_id="v1",
            available=False,
        )

    ragflow.set_document_chunk_available.assert_awaited_once_with("ds1", "doc1", "c1", False)
    audit.assert_awaited_once()
    assert result.available is False
    assert result.chunk_id == "c1"
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_set_available_uncertain_on_transport():
    db = MagicMock()
    db.get = AsyncMock(return_value=_version())
    member = _member()
    ragflow = AsyncMock()
    ragflow.set_document_chunk_available = AsyncMock(
        side_effect=RagflowError(
            "unknown",
            message_key="errors.knowledge.chunk_mutation_uncertain",
            status_code=503,
        )
    )
    kb = SimpleNamespace(id="kb1", deleted_at=None)

    with (
        patch(
            "app.services.source_chunk_service.source_file_service.get_source_file",
            new=AsyncMock(return_value=_sf()),
        ),
        patch(
            "app.services.source_chunk_service._require_update_or_manage",
            new=AsyncMock(),
        ),
        patch(
            "app.services.source_chunk_service.knowledge_base_service.get_knowledge_base",
            new=AsyncMock(return_value=kb),
        ),
        patch(
            "app.services.source_chunk_service.runtime_binding_service.get_dataset_id",
            new=AsyncMock(return_value="ds1"),
        ),
    ):
        with pytest.raises(ServiceUnavailableError) as ei:
            await source_chunk_service.set_source_file_chunk_available(
                db,
                member,
                ragflow,
                "sf1",
                "c1",
                file_version_id="v1",
                available=False,
            )
    assert ei.value.message_key == "errors.knowledge.chunk_mutation_uncertain"

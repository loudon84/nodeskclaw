"""API v2 Evidence endpoint tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v2 import evidence
from app.api.v2.evidence import router as evidence_router
from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.schemas.principal import KnowledgePrincipal


def _member() -> KnowledgePrincipal:
    return KnowledgePrincipal(
        user_id="u1",
        member_id="m1",
        org_id="o1",
        member_role="member",
    )


def test_v2_router_mounts_evidence_route():
    assert any("/evidence/{evidence_id}" in (getattr(r, "path", "") or "") for r in evidence_router.routes)


@pytest.mark.asyncio
async def test_get_evidence_v2_disabled(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_API_V2_ENABLED", False)
    with pytest.raises(BadRequestError) as exc:
        await evidence.get_evidence("ev1", member=_member(), db=AsyncMock())
    assert exc.value.message_key == "errors.knowledge.api_v2_disabled"


@pytest.mark.asyncio
async def test_get_evidence_returns_resolve_payload(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_API_V2_ENABLED", True)
    payload = {
        "evidence_id": "ev1",
        "citation_id": "ev1",
        "message_id": None,
        "org_id": "o1",
        "issued_member_id": "m1",
        "evidence_type": "chunk",
        "content": "hello",
        "source_refs": [{"source_file_id": "sf1"}],
        "origin": "direct_retrieval",
        "knowledge_base_id": "kb1",
        "source_file_id": "sf1",
        "file_version_id": "v1",
        "document_id": "doc1",
        "chunk_id": "chunk1",
        "page": 1,
        "positions": None,
        "score": 0.9,
        "quote": "hello",
        "accessible": True,
        "reason": "ok",
        "source_kind": "manual",
        "connector_type": None,
        "connector_name": None,
        "source_path": "/a.pdf",
        "source_revision": None,
        "source_modified_at": None,
        "last_synced_at": None,
        "sync_state": "in_sync",
        "source_freshness": "fresh",
    }
    with patch(
        "app.api.v2.evidence.citation_service.resolve_citation",
        new=AsyncMock(return_value=payload),
    ):
        resp = await evidence.get_evidence("ev1", member=_member(), db=MagicMock())

    assert resp.data.evidence_id == "ev1"
    assert resp.data.message_id is None
    assert resp.data.accessible is True
    assert resp.data.document_id is None

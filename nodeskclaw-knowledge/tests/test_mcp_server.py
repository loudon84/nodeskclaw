"""MCP transport tests — reuses agent_tools service paths with member principal."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.mcp_server import MCP_TOOL_NAMES, call_tool, list_tools
from app.schemas.principal import KnowledgePrincipal

MEMBER = KnowledgePrincipal(
    user_id="user-1",
    member_id="member-1",
    org_id="org-1",
    name="Test User",
)


def test_mcp_lists_four_knowledge_tools():
    names = {tool.name for tool in list_tools()}
    assert names == set(MCP_TOOL_NAMES)


def test_v2_router_mounts_mcp_routes():
    from app.api.v2.router import router as v2_router
    from app.mcp_server import router as mcp_router

    included_routers = [getattr(r, "original_router", None) for r in v2_router.routes]
    assert mcp_router in included_routers

    paths = [getattr(r, "path", "") or "" for r in mcp_router.routes]
    assert any("/tools/list" in path for path in paths)
    assert any("/tools/call" in path for path in paths)


def test_mcp_routes_require_member_context_dependency():
    from app.mcp_server import router as mcp_router

    for route in mcp_router.routes:
        deps = getattr(route, "dependant", None)
        if deps is None:
            continue
        names = [d.name for d in deps.dependencies if getattr(d, "name", None)]
        if "/mcp/tools/" in route.path:
            assert "member" in names


def test_mcp_tools_call_without_auth_rejected():
    with TestClient(app) as client:
        resp = client.post("/api/v2/mcp/tools/call", json={"name": "knowledge.search", "arguments": {}})
    assert resp.status_code == 401


def test_mcp_tools_list_without_auth_rejected():
    with TestClient(app) as client:
        resp = client.post("/api/v2/mcp/tools/list")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_mcp_search_matches_http_semantics(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_API_V2_ENABLED", True)
    retrieval_payload = {
        "chunks": [{"content": "hello", "document_id": "runtime-doc-1"}],
        "evidence": [{"payload": {"document_id": "runtime-doc-2", "text": "ev"}}],
    }

    with patch(
        "app.api.agent_tools.retrieval_service.retrieve_for_application",
        new=AsyncMock(return_value=retrieval_payload),
    ) as retrieve_mock:
        mcp_result = await call_tool(
            AsyncMock(),
            MEMBER,
            MagicMock(),
            name="knowledge.search",
            arguments={"query": "hello", "application_id": "app-1", "top_k": 3},
        )

    retrieve_mock.assert_awaited_once()
    assert mcp_result["chunks"][0]["content"] == "hello"
    assert "document_id" not in mcp_result["chunks"][0]
    assert "document_id" not in mcp_result["evidence"][0]["payload"]


@pytest.mark.asyncio
async def test_mcp_get_document_strips_runtime_ids(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_API_V2_ENABLED", True)
    sf = MagicMock()
    sf.id = "sf-1"
    sf.name = "doc.pdf"
    sf.status = "active"
    sf.active_version_id = "ver-1"
    sf.knowledge_base_id = "kb-1"

    with patch(
        "app.api.agent_tools.source_file_service.get_source_file",
        new=AsyncMock(return_value=sf),
    ):
        result = await call_tool(
            AsyncMock(),
            MEMBER,
            MagicMock(),
            name="knowledge.get_document",
            arguments={"source_file_id": "sf-1"},
        )

    assert result == {
        "source_file_id": "sf-1",
        "name": "doc.pdf",
        "status": "active",
        "active_version_id": "ver-1",
        "knowledge_base_id": "kb-1",
    }


@pytest.mark.asyncio
async def test_mcp_get_evidence_uses_citation_resolve(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_API_V2_ENABLED", True)
    citation_payload = {
        "evidence_id": "ev-1",
        "text": "cited text",
        "document_id": "runtime-doc",
        "ragflow_document_id": "rf-doc",
    }

    with patch(
        "app.api.agent_tools.citation_service.resolve_citation",
        new=AsyncMock(return_value=citation_payload),
    ) as resolve_mock:
        result = await call_tool(
            AsyncMock(),
            MEMBER,
            MagicMock(),
            name="knowledge.get_evidence",
            arguments={"evidence_id": "ev-1"},
        )

    resolve_mock.assert_awaited_once()
    assert result["evidence_id"] == "ev-1"
    assert "document_id" not in result
    assert "ragflow_document_id" not in result


@pytest.mark.asyncio
async def test_mcp_http_call_with_auth(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_API_V2_ENABLED", True)
    retrieval_payload = {"chunks": [], "evidence": []}

    with (
        patch(
            "app.core.deps.NodeskclawBackendClient.fetch_knowledge_context",
            new=AsyncMock(return_value=MEMBER),
        ),
        patch(
            "app.mcp_server.call_tool",
            new=AsyncMock(return_value=retrieval_payload),
        ),
    ):
        with TestClient(app) as client:
            resp = client.post(
                "/api/v2/mcp/tools/call",
                headers={"Authorization": "Bearer test-token"},
                json={
                    "name": "knowledge.search",
                    "arguments": {"query": "hello", "application_id": "app-1"},
                },
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    content_text = body["data"]["content"][0]["text"]
    assert json.loads(content_text) == retrieval_payload

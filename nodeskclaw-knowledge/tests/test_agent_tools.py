"""Agent tools require member context dependency."""

from app.api import agent_tools
from app.api.agent_tools import SearchBody
from app.api.v2.evidence import router as evidence_router
from app.mcp_server import MCP_TOOL_NAMES


def test_agent_tools_use_member_context_dependency():
    # FastAPI may store path without prefix depending on include order
    assert any("knowledge.search" in (getattr(r, "path", "") or "") for r in agent_tools.router.routes)
    assert any("knowledge.retrieve" in (getattr(r, "path", "") or "") for r in agent_tools.router.routes)
    assert any("knowledge.get_document" in (getattr(r, "path", "") or "") for r in agent_tools.router.routes)
    assert any("knowledge.get_evidence" in (getattr(r, "path", "") or "") for r in agent_tools.router.routes)
    assert any("/evidence/{evidence_id}" in (getattr(r, "path", "") or "") for r in evidence_router.routes)
    for route in agent_tools.router.routes:
        deps = getattr(route, "dependant", None)
        if deps is None:
            continue
        names = [d.name for d in deps.dependencies if getattr(d, "name", None)]
        if "knowledge.search" in route.path or "knowledge.retrieve" in route.path:
            assert "member" in names
        if "knowledge.get_evidence" in route.path:
            assert "member" in names


def test_knowledge_retrieve_shares_search_route_and_member_dep():
    search_routes = [
        r for r in agent_tools.router.routes if "knowledge.search" in (getattr(r, "path", "") or "")
    ]
    retrieve_routes = [
        r for r in agent_tools.router.routes if "knowledge.retrieve" in (getattr(r, "path", "") or "")
    ]
    assert search_routes
    assert retrieve_routes
    # Same handler endpoints are registered; both require member principal.
    for route in [*search_routes, *retrieve_routes]:
        deps = getattr(route, "dependant", None)
        assert deps is not None
        names = [d.name for d in deps.dependencies if getattr(d, "name", None)]
        assert "member" in names


def test_search_body_exposes_plugin_v1_fields():
    fields = SearchBody.model_fields
    assert "knowledge_set_id" in fields
    assert "query" in fields
    assert "top_k" in fields
    # Plugin v1.0 does not send application_id; field remains optional on the API.
    assert "application_id" in fields
    assert fields["application_id"].is_required() is False


def test_mcp_tools_cover_agent_tool_names():
    assert set(MCP_TOOL_NAMES) == {
        "knowledge.search",
        "knowledge.retrieve",
        "knowledge.get_document",
        "knowledge.get_evidence",
        "knowledge.get_structure",
        "knowledge.get_table",
    }

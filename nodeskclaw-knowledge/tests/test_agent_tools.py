"""Agent tools require member context dependency."""

from app.api import agent_tools


def test_agent_tools_use_member_context_dependency():
    routes = {route.path: route for route in agent_tools.router.routes}
    search = routes.get("/agent/tools/knowledge.search") or routes.get("/knowledge.search")
    # FastAPI may store path without prefix depending on include order
    assert any("knowledge.search" in (getattr(r, "path", "") or "") for r in agent_tools.router.routes)
    assert any("knowledge.get_document" in (getattr(r, "path", "") or "") for r in agent_tools.router.routes)
    for route in agent_tools.router.routes:
        deps = getattr(route, "dependant", None)
        if deps is None:
            continue
        names = [d.name for d in deps.dependencies if getattr(d, "name", None)]
        if "knowledge.search" in route.path or "knowledge.retrieve" in route.path:
            assert "member" in names

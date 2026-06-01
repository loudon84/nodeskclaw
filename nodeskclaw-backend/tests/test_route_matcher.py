import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.services.gateway.route_matcher import RouteMatcher
from app.services.gateway.types import UpstreamTarget


def _make_route(instance_id, name, mcp_server_ids, match_tools=None, priority=0, org_id="org1"):
    route = MagicMock()
    route.instance_id = instance_id
    route.name = name
    route.mcp_server_ids = mcp_server_ids
    route.match_tools = match_tools or []
    route.priority = priority
    route.org_id = org_id
    route.is_active = True
    return route


class TestRouteMatcher:
    def test_exact_tool_match(self):
        matcher = RouteMatcher()
        route = _make_route("inst1", "r1", ["s1"], match_tools=["file_read"])
        matcher._routes = [route]
        result = matcher.match("inst1", "file_read", "org1")
        assert len(result) == 1
        assert result[0].mcp_server_id == "s1"

    def test_wildcard_match(self):
        matcher = RouteMatcher()
        route = _make_route("inst1", "r1", ["s1"], match_tools=["file_*"])
        matcher._routes = [route]
        result = matcher.match("inst1", "file_write", "org1")
        assert len(result) == 1

    def test_no_match_tools_matches_all(self):
        matcher = RouteMatcher()
        route = _make_route("inst1", "r1", ["s1", "s2"])
        matcher._routes = [route]
        result = matcher.match("inst1", "any_tool", "org1")
        assert len(result) == 2

    def test_priority_order(self):
        matcher = RouteMatcher()
        low = _make_route("inst1", "low", ["s1"], match_tools=["*"], priority=0)
        high = _make_route("inst1", "high", ["s2"], match_tools=["file_*"], priority=10)
        matcher._routes = [high, low]
        result = matcher.match("inst1", "file_read", "org1")
        assert result[0].mcp_server_id == "s2"

    def test_no_matching_route(self):
        matcher = RouteMatcher()
        route = _make_route("inst1", "r1", ["s1"], match_tools=["other_*"])
        matcher._routes = [route]
        result = matcher.match("inst1", "file_read", "org1")
        assert len(result) == 0

    def test_org_id_filter(self):
        matcher = RouteMatcher()
        route = _make_route("inst1", "r1", ["s1"], org_id="org1")
        matcher._routes = [route]
        result = matcher.match("inst1", None, "org2")
        assert len(result) == 0

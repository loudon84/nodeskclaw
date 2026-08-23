from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.expert_gateway.expert_mcp_auth_guard import (
    ExpertMcpAuthGuard,
    MCP_SCOPE_TOOLS_CALL,
    MCP_SCOPE_TOOLS_LIST,
)
from app.services.expert_gateway.errors import EXPERT_SCOPE_DENIED, EXPERT_TOOL_NOT_ALLOWED
from app.services.mcp_skill_gateway.auth import McpAuthContext


def _token_ctx(*, scopes=None, allowed_tools=None, allowed_skills=None):
    return McpAuthContext(
        user=SimpleNamespace(id="user-1"),
        org=SimpleNamespace(id="org-1"),
        auth_type="mcp_client_token",
        scopes=list(scopes or ["mcp:tools:list", "mcp:tools:call"]),
        allowed_tools=allowed_tools,
        allowed_skills=allowed_skills,
    )


def test_require_scope_denies_missing_tools_list():
    err = ExpertMcpAuthGuard.require_scope(_token_ctx(scopes=["mcp:tools:call"]), MCP_SCOPE_TOOLS_LIST, "1")
    assert err is not None
    assert err["error"]["data"]["errorCode"] == EXPERT_SCOPE_DENIED


def test_filter_catalog_tools_by_allowed_tools():
    tools = [{"name": "a"}, {"name": "b"}]
    filtered = ExpertMcpAuthGuard.filter_catalog_tools(tools, _token_ctx(allowed_tools=["b"]))
    assert [item["name"] for item in filtered] == ["b"]


def test_assert_skill_allowed_blocks_unlisted_skill():
    err = ExpertMcpAuthGuard.assert_skill_allowed(
        _token_ctx(allowed_skills=["skill.a"]),
        "skill.b",
        "1",
    )
    assert err is not None
    assert err["error"]["data"]["errorCode"] == EXPERT_TOOL_NOT_ALLOWED


@pytest.mark.asyncio
async def test_dispatch_root_filters_catalog_tools():
    from unittest.mock import patch

    from app.services.expert_gateway.expert_mcp_gateway_service import ExpertMcpGatewayService

    db = AsyncMock()
    gateway = ExpertMcpGatewayService(db)
    gateway.catalog.list_published_experts = AsyncMock(return_value=[])
    gateway.teams.list_published_teams = AsyncMock(return_value=[])
    auth = _token_ctx(scopes=["mcp:tools:list"], allowed_tools=["missing-slug"])

    with patch(
        "app.services.expert_gateway.expert_mcp_gateway_service.ExpertPermissionService.has",
        new=AsyncMock(return_value=True),
    ):
        result = await gateway.dispatch_root(
            auth,
            {"jsonrpc": "2.0", "id": "1", "method": "tools/list"},
        )
    assert result["result"]["tools"] == []

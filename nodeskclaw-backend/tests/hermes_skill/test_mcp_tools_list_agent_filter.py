import pytest
from unittest.mock import AsyncMock, patch

from app.services.mcp_skill_gateway.handler import _handle_tools_list


@pytest.mark.asyncio
async def test_tools_list_rejects_agent_alias_filter():
    db = AsyncMock()
    with patch(
        "app.services.mcp_skill_gateway.handler._collect_tools",
        AsyncMock(return_value=[{"name": "writer_article_generate"}]),
    ) as collect:
        result = await _handle_tools_list(
            1,
            "user-1",
            "org-1",
            db,
            params={"agent_alias": "common-writer", "profile": "writer"},
            request_headers={},
        )
    collect.assert_not_awaited()
    assert "error" in result
    assert result["error"]["data"]["errorCode"] == "MCP_INVALID_ARGUMENTS"


@pytest.mark.asyncio
async def test_tools_list_ignores_profile_header_without_params():
    db = AsyncMock()
    with patch(
        "app.services.mcp_skill_gateway.handler._collect_tools",
        AsyncMock(return_value=[]),
    ) as collect:
        result = await _handle_tools_list(
            1,
            "user-1",
            "org-1",
            db,
            params={},
            request_headers={"X-NoDeskClaw-Hermes-Profile": "writer"},
        )
    collect.assert_awaited_once_with(
        "user-1",
        "org-1",
        db,
        allowed_skills=None,
    )
    assert result["result"]["tools"] == []

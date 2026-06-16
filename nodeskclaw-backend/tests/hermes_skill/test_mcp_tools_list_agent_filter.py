import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.mcp_skill_gateway.handler import _handle_tools_list


@pytest.mark.asyncio
async def test_tools_list_agent_alias_filter():
    db = AsyncMock()
    with patch("app.services.mcp_skill_gateway.handler._collect_tools", AsyncMock(return_value=[{"name": "writer_article_generate"}])) as collect:
        result = await _handle_tools_list(
            1,
            "user-1",
            "org-1",
            db,
            params={"agent_alias": "common-writer", "profile": "writer"},
            request_headers={},
        )
    collect.assert_awaited_once_with(
        "user-1",
        "org-1",
        db,
        agent_alias="common-writer",
        profile="writer",
        workspace_id=None,
    )
    assert result["result"]["tools"][0]["name"] == "writer_article_generate"


@pytest.mark.asyncio
async def test_tools_list_profile_header_fallback():
    db = AsyncMock()
    with patch("app.services.mcp_skill_gateway.handler._collect_tools", AsyncMock(return_value=[])) as collect:
        await _handle_tools_list(
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
        agent_alias=None,
        profile="writer",
        workspace_id=None,
    )

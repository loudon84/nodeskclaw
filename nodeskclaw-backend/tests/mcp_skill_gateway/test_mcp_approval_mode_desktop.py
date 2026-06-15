import pytest
from unittest.mock import AsyncMock

from app.services.mcp_skill_gateway.approval_service import check_tool_grant, get_grant_annotation
from app.services.mcp_skill_gateway.mcp_tool_registry import get_tool


@pytest.mark.asyncio
async def test_desktop_mode_skips_server_approval():
    tool = get_tool("genehub.skill.register_to_hermes")
    assert tool is not None
    db = AsyncMock()
    result = await check_tool_grant(
        db,
        org_id="org-1",
        user_id="user-1",
        tool=tool,
        instance_id=None,
        instance_ref=None,
    )
    assert result.allowed is True


@pytest.mark.asyncio
async def test_none_mode_skips_server_approval():
    tool = get_tool("genehub.skills.search")
    assert tool is not None
    db = AsyncMock()
    result = await check_tool_grant(
        db,
        org_id="org-1",
        user_id="user-1",
        tool=tool,
        instance_id=None,
        instance_ref=None,
    )
    assert result.allowed is True


@pytest.mark.asyncio
async def test_desktop_mode_grant_annotation():
    tool = get_tool("genehub.skill.register_to_hermes")
    assert tool is not None
    db = AsyncMock()
    annotation = await get_grant_annotation(
        db,
        org_id="org-1",
        user_id="user-1",
        instance_id=None,
        tool_name=tool.name,
        tool=tool,
    )
    assert annotation["authorized"] is True
    assert annotation["grantStatus"] == "desktop_pending"
    assert annotation["approvalMode"] == "desktop"
